"""ACO explorer window with repeatable random city generation.

Run from the repository root with ``python -m visualization.app``.
Romania county seats can be selected on an offline geographic map.
"""

import tkinter as tk
from tkinter import ttk
from queue import Empty, Queue
from threading import Thread

from algorithm.aco import Config, Result
from algorithm.tsp import City
from algorithm.visualize_solution import scale_city_positions, scale_history
from .datasets import generate_random_cities
from .runner import run_solver
from .romania_map import RomaniaMap
from .tours import with_start_city


DATASETS = ("Random cities", "Romania - county seats", "USA - state capitals")
DEFAULTS = {
    "city_count": "20",
    "seed": "7",
    "alpha": "1.0",
    "beta": "3.0",
    "rho": "0.4",
    "ants": "0",
    "iterations": "100",
}
PLAYBACK_SPEEDS = {"Slow (700 ms)": 700, "Normal (300 ms)": 300, "Fast (100 ms)": 100}


def read_settings(values: dict[str, str]) -> tuple[int, int, Config]:
    """Convert entry text into validated values, without depending on widgets."""
    parsed = {}
    for name in DEFAULTS:
        convert = float if name in ("alpha", "beta", "rho") else int
        try:
            parsed[name] = convert(values[name])
        except ValueError:
            kind = "a number" if convert is float else "a whole number"
            raise ValueError(f"{name.replace('_', ' ').capitalize()} must be {kind}.") from None
    if parsed["city_count"] < 2:
        raise ValueError("City count must be at least 2.")
    config = Config(
        alpha=parsed["alpha"], beta=parsed["beta"], rho=parsed["rho"],
        ants=parsed["ants"], iterations=parsed["iterations"],
    )
    return parsed["city_count"], parsed["seed"], config


class ExplorerApp:
    """Own the window and form state; algorithm logic stays in algorithm/."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("ACO Route Explorer")
        # Allow space for a geographic map on larger displays, while fitting
        # smaller screens. Users can still maximize or resize the window.
        initial_width = min(1180, root.winfo_screenwidth() - 80)
        initial_height = min(920, root.winfo_screenheight() - 100)
        root.geometry(f"{initial_width}x{initial_height}")
        root.minsize(900, 680)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.dataset = tk.StringVar(value=DATASETS[0])
        self.fields = {name: tk.StringVar(value=value) for name, value in DEFAULTS.items()}
        self.cities: list[City] = []
        self.romania_map = None
        self.selected_ids: set[str] = set()
        self.selection_order: list[str] = []
        self.selected_seats = []
        self.selection_label = tk.StringVar(value="")
        self.start_label = tk.StringVar(value="Start: --")
        self.map_hint = tk.StringVar(value="Random cities use schematic coordinates.")
        self.loaded_seed: int | None = None
        self.result: Result | None = None
        self.running = False
        self.playing = False
        self.animation_after = None
        self.animate_iterations = tk.BooleanVar(value=False)
        self.playback_speed = tk.StringVar(value="Normal (300 ms)")
        self.messages: Queue[Result | Exception] = Queue()
        self.iteration = tk.DoubleVar(value=1)
        self.iteration_label = tk.StringVar(value="No run selected")
        self.input_widgets = []
        self.status = tk.StringVar(value="Choose a city count and seed, then generate cities.")
        self.feedback = tk.StringVar(value="Enter parameters, then check settings.")
        self.best_distance = tk.StringVar(value="Best distance: --")

        shell = ttk.Frame(root, padding=18)
        shell.grid(sticky="nsew")
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(2, weight=3)
        shell.rowconfigure(3, weight=0)

        ttk.Label(shell, text="ACO Route Explorer", font=("Segoe UI", 22, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(shell, text="Explore how ant colony optimization finds a closed city tour.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 18))

        self._build_controls(shell)
        self._build_display(shell)
        root.protocol("WM_DELETE_WINDOW", self._close)
        ttk.Label(shell, textvariable=self.status, wraplength=820).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _build_controls(self, parent):
        controls = ttk.LabelFrame(parent, text="Dataset and parameters", padding=14)
        controls.grid(row=2, column=0, rowspan=2, sticky="nsew", padx=(0, 16))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Dataset").grid(row=0, column=0, columnspan=2, sticky="w")
        selector = ttk.Combobox(
            controls, textvariable=self.dataset, values=DATASETS, state="readonly", width=27)
        selector.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 14))
        selector.bind("<<ComboboxSelected>>", self._dataset_changed)
        self.selector = selector

        labels = (
            ("city_count", "Random city count"), ("seed", "Seed"),
            ("alpha", "Alpha"), ("beta", "Beta"), ("rho", "Rho"),
            ("ants", "Ants"), ("iterations", "Iterations"),
        )
        for row, (name, label) in enumerate(labels, start=2):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=5)
            entry = ttk.Entry(controls, textvariable=self.fields[name], width=12)
            entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
            self.input_widgets.append(entry)
            if name == "city_count":
                self.city_count_entry = entry

        ttk.Label(controls, text="Ants = 0: one ant per city.\nQ is fixed at 100.").grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(8, 12))
        self.check_button = ttk.Button(controls, text="Check settings", command=self.check_settings)
        self.check_button.grid(row=10, column=0, columnspan=2, sticky="ew")
        ttk.Label(controls, textvariable=self.feedback, wraplength=240).grid(
            row=11, column=0, columnspan=2, sticky="w", pady=10)

        actions = ttk.Frame(controls)
        actions.grid(row=12, column=0, columnspan=2, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        self.start_button = ttk.Button(actions, text="Start", command=self.start_run, state="disabled")
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.reset_button = ttk.Button(actions, text="Reset form", command=self.reset_form)
        self.reset_button.grid(row=0, column=1, sticky="ew")
        ttk.Label(controls, text="Generate or select cities, then Start.\nReruns use the same city selection.",
                  wraplength=240).grid(row=13, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.generate_button = ttk.Button(
            controls, text="Generate cities", command=self.generate_cities)
        self.generate_button.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(controls, text="Count applies on Generate cities.\nSeed also controls solver randomness.",
                  wraplength=240).grid(row=15, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_display(self, parent):
        map_frame = ttk.LabelFrame(parent, text="City map", padding=8)
        map_frame.grid(row=2, column=1, sticky="nsew")
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=0)
        map_frame.rowconfigure(1, weight=1)
        self.selection_toolbar = ttk.Frame(map_frame)
        self.selection_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.select_all_button = ttk.Button(
            self.selection_toolbar, text="Select all", command=lambda: self._select_all_seats(True))
        self.select_all_button.grid(row=0, column=0)
        self.clear_selection_button = ttk.Button(
            self.selection_toolbar, text="Clear selection", command=lambda: self._select_all_seats(False))
        self.clear_selection_button.grid(row=0, column=1, padx=6)
        ttk.Label(self.selection_toolbar, textvariable=self.selection_label).grid(row=0, column=2, sticky="w")
        ttk.Label(self.selection_toolbar, textvariable=self.start_label).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.selection_toolbar.grid_remove()
        self.map_canvas = tk.Canvas(map_frame, background="#eef3f7", highlightthickness=0)
        self.map_canvas.grid(row=1, column=0, sticky="nsew")
        self.map_canvas.bind("<Configure>", self._draw_map)
        self.map_canvas.bind("<Button-1>", self._map_clicked)
        self.map_canvas.bind("<Motion>", self._map_hover)
        ttk.Label(map_frame, textvariable=self.map_hint, wraplength=650).grid(row=2, column=0, sticky="w", pady=(3, 0))
        self.attribution = ttk.Label(map_frame, text="Boundaries: geoBoundaries / World Bank (CC BY 4.0). Cities: GeoNames / Călărași council.",
                                     font=("Segoe UI", 8), wraplength=650)
        self.attribution.grid(row=3, column=0, sticky="w")
        self.attribution.grid_remove()

        results = ttk.LabelFrame(parent, text="Results", padding=10)
        results.grid(row=3, column=1, sticky="nsew", pady=(12, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        ttk.Label(results, textvariable=self.best_distance).grid(row=0, column=0, sticky="w")
        self.chart = tk.Canvas(results, height=140, background="white", highlightthickness=0)
        self.chart.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.chart.bind("<Configure>", self._draw_chart)
        ttk.Label(results, textvariable=self.iteration_label).grid(
            row=2, column=0, sticky="w", pady=(6, 0))
        self.slider = ttk.Scale(results, from_=1, to=1, variable=self.iteration,
                                command=self._select_iteration, state="disabled")
        self.slider.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        playback = ttk.Frame(results)
        playback.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            playback, text="Animate iterations (replay)", variable=self.animate_iterations,
            command=self._animation_option_changed).grid(row=0, column=0, sticky="w")
        self.play_button = ttk.Button(
            playback, text="Play", command=self.toggle_playback, state="disabled")
        self.play_button.grid(row=0, column=1, padx=8)
        self.speed_selector = ttk.Combobox(
            playback, textvariable=self.playback_speed, values=tuple(PLAYBACK_SPEEDS),
            state="disabled", width=18)
        self.speed_selector.grid(row=0, column=2)
        self.route_text = tk.Text(results, height=2, wrap="word", state="disabled",
                                  font=("Segoe UI", 9), relief="flat")
        self.route_text.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        route_scroll = ttk.Scrollbar(results, orient="vertical", command=self.route_text.yview)
        route_scroll.grid(row=5, column=1, sticky="ns", pady=(6, 0))
        self.route_text.configure(yscrollcommand=route_scroll.set)

    def _draw_map(self, event=None):
        """Redraw from stored coordinates; resizing never regenerates cities."""
        self.map_canvas.delete("all")
        width, height = self.map_canvas.winfo_width(), self.map_canvas.winfo_height()
        if self.dataset.get() == DATASETS[1] and self.romania_map is not None:
            tour_ids = ()
            if self.result:
                tour_ids = tuple(self.selected_seats[i].id
                                 for i in self.result.tour_history[self._iteration_index()])
            start_id = self.selection_order[0] if self.selection_order else None
            self.romania_map.draw(self.map_canvas, self.selected_ids, tour_ids, start_id=start_id)
            return
        if self.cities:
            # Tkinter may briefly report a tiny canvas while laying out widgets.
            if width <= 80 or height <= 80:
                return
            positions = scale_city_positions(self.cities, width, height)
            start_city = None
            if self.result:
                tour = self.result.tour_history[self._iteration_index()]
                start_city = tour[0]
                for index, city in enumerate(tour):
                    next_city = tour[(index + 1) % len(tour)]
                    self.map_canvas.create_line(
                        *positions[city], *positions[next_city],
                        fill="#3274a1", width=2, arrow=tk.LAST, tags="route-edge")
            for index, (x, y) in enumerate(positions):
                self.map_canvas.create_oval(
                    x - 5, y - 5, x + 5, y + 5,
                    fill="#d66a24" if index == start_city else "#3274a1",
                    outline="white", width=1, tags="city-marker")
                self.map_canvas.create_text(
                    x + 9, y - 10, text=str(index), anchor="sw",
                    fill="#24374b", tags="city-label")
            self.map_canvas.create_text(
                12, 12, anchor="nw", fill="#44576b",
                text=f"{len(self.cities)} random cities | seed {self.loaded_seed} | schematic coordinates")
            return
        message = (
            "Choose a count and seed, then click Generate cities."
            if self.dataset.get() == DATASETS[0]
            else "This geographic dataset and its map outline are not loaded yet."
        )
        self.map_canvas.create_text(
            width / 2, height / 2, width=max(100, width - 50), justify="center",
            text=f"{self.dataset.get()}\n\n{message}",
            fill="#44576b", font=("Segoe UI", 13))

    def _draw_chart(self, event=None):
        self.chart.delete("all")
        width, height = self.chart.winfo_width(), self.chart.winfo_height()
        if self.result and width > 90 and height > 90:
            points = scale_history(self.result.history, width, height)
            self.chart.create_line(45, 20, 45, height - 35, width - 20, height - 35,
                                   fill="#657589")
            self.chart.create_text(width / 2, height - 12, text="Iteration", fill="#44576b")
            self.chart.create_text(12, height / 2, text="Distance", angle=90, fill="#44576b")
            self.chart.create_text(48, 12, anchor="nw",
                                   text=f"Best-so-far: {self.result.history[0]:.4f} → {self.result.best_length:.4f}")
            if len(points) > 1:
                self.chart.create_line(*[value for point in points for value in point],
                                       fill="#3274a1", width=2)
            x, y = points[self._iteration_index()]
            self.chart.create_line(x, 35, x, height - 35, fill="#d66a24", dash=(3, 3))
            self.chart.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#d66a24", outline="")
            return
        self.chart.create_text(
            width / 2, height / 2,
            text="Convergence: best distance per iteration", fill="#657589")

    def _set_route_text(self, text):
        self.route_text.configure(state="normal")
        self.route_text.delete("1.0", "end")
        self.route_text.insert("1.0", text)
        self.route_text.configure(state="disabled")

    def _iteration_index(self):
        return max(0, min(len(self.result.history) - 1, int(round(self.iteration.get())) - 1))

    def _select_iteration(self, value=None):
        if self.result is None:
            return
        # The scale supplies a value for user input; playback calls with no value.
        if value is not None and self.playing:
            self._pause_animation()
            self.status.set("Replay paused. Inspect an iteration or press Play to continue.")
        index = self._iteration_index()
        self.iteration_label.set(
            f"Iteration {index + 1}/{len(self.result.history)} | "
            f"best-so-far distance: {self.result.history[index]:.4f} {self._distance_unit()}")
        tour = self.result.tour_history[index]
        names = ([self.selected_seats[i].name for i in tour] if self.dataset.get() == DATASETS[1]
                 else [str(i) for i in tour])
        self._set_route_text(" → ".join(names + names[:1]))
        self._draw_map()
        self._draw_chart()

    def _clear_result(self):
        self._pause_animation()
        self.result = None
        self.best_distance.set("Best distance: --")
        self.slider.configure(state="disabled", to=1)
        self.iteration.set(1)
        self.iteration_label.set("No run selected")
        self._set_route_text("")
        self._draw_chart()
        self._sync_playback_controls()

    def _sync_playback_controls(self):
        enabled = self.animate_iterations.get()
        can_play = enabled and not self.running and self.result is not None and len(self.result.history) > 1
        self.play_button.configure(state="normal" if can_play else "disabled",
                                   text="Pause" if self.playing else "Play")
        self.speed_selector.configure(state="readonly" if enabled else "disabled")

    def _pause_animation(self):
        """Cancel the scheduled frame so old playback cannot change a new run."""
        if self.animation_after is not None:
            self.root.after_cancel(self.animation_after)
            self.animation_after = None
        self.playing = False
        self.play_button.configure(text="Play")

    def _animation_option_changed(self):
        if not self.animate_iterations.get():
            self._pause_animation()
            if self.result is not None:
                self.status.set("Animation disabled. Use the slider to inspect the saved history.")
        self._sync_playback_controls()

    def toggle_playback(self):
        if self.playing:
            self._pause_animation()
            self.status.set("Replay paused. Press Play to continue.")
            return
        if (self.running or not self.animate_iterations.get() or self.result is None
                or len(self.result.history) < 2):
            return
        # Play at the final iteration means replay from the beginning.
        if self._iteration_index() == len(self.result.history) - 1:
            self.iteration.set(1)
        self.playing = True
        self._sync_playback_controls()
        self._select_iteration()
        self.status.set("Replaying saved best-so-far tours. Pause or move the slider to inspect a step.")
        self._schedule_frame()

    def _schedule_frame(self):
        delay = PLAYBACK_SPEEDS[self.playback_speed.get()]
        self.animation_after = self.root.after(delay, self._advance_frame)

    def _advance_frame(self):
        self.animation_after = None
        if not self.playing or self.result is None:
            return
        index = self._iteration_index()
        if index < len(self.result.history) - 1:
            self.iteration.set(index + 2)
            self._select_iteration()
        if self._iteration_index() == len(self.result.history) - 1:
            self._pause_animation()
            self.status.set("Replay complete. Press Play to replay from iteration 1.")
        else:
            self._schedule_frame()

    def _close(self):
        self._pause_animation()
        self.root.destroy()

    def _dataset_changed(self, event=None):
        if self.running:
            return
        random_cities = self.dataset.get() == DATASETS[0]
        self.city_count_entry.configure(state="normal" if random_cities else "disabled")
        self.generate_button.configure(state="normal" if random_cities else "disabled")
        self.cities = []
        self.selected_ids = set()
        self.selection_order = []
        self.selected_seats = []
        self.start_label.set("Start: --")
        self.loaded_seed = None
        self._clear_result()
        self.start_button.configure(state="disabled")
        self.feedback.set("Enter parameters, then check settings.")
        self.status.set(
            "Choose a city count and seed, then generate cities." if random_cities
            else f"Selected {self.dataset.get()}. This dataset is not loaded yet.")
        if self.dataset.get() == DATASETS[1]:
            try:
                if self.romania_map is None:
                    self.romania_map = RomaniaMap()
            except (OSError, ValueError, KeyError) as error:
                self.status.set(f"Could not load Romania map: {error}")
                return
            self.selection_toolbar.grid()
            self.attribution.grid()
            self.selection_label.set(f"0 / {len(self.romania_map.seats)} cities selected")
            self.map_hint.set("First selected city is the start (orange). Click markers to select or deselect cities.")
            self.status.set("Romania loaded. Select at least two county seats on the map, then press Start.")
        else:
            self.selection_toolbar.grid_remove()
            self.attribution.grid_remove()
            self.map_hint.set("Random cities use schematic coordinates." if random_cities else "US state capitals are not loaded yet.")
        self._draw_map()

    def _distance_unit(self):
        return "km (geographic)" if self.dataset.get() == DATASETS[1] else "coordinate units"

    def _map_clicked(self, event):
        if self.running or self.dataset.get() != DATASETS[1] or self.romania_map is None:
            return
        city_id = self.romania_map.hit_test(event.x, event.y)
        if city_id is None:
            return
        if city_id in self.selected_ids:
            self.selected_ids.remove(city_id)
        else:
            self.selected_ids.add(city_id)
            self.selection_order.append(city_id)
        self._selection_changed()

    def _map_hover(self, event):
        if self.dataset.get() != DATASETS[1] or self.romania_map is None:
            return
        city_id = self.romania_map.hit_test(event.x, event.y)
        self.map_canvas.configure(cursor="hand2" if city_id and not self.running else "")
        seat = next((seat for seat in self.romania_map.seats if seat.id == city_id), None)
        self.map_hint.set(
            f"{seat.name} — {seat.county} ({seat.id}). "
            + ("Starting city." if self.selection_order and seat.id == self.selection_order[0]
               else "Selected." if seat.id in self.selected_ids else "Click to select.") if seat
            else "First selected city is the start (orange). Click markers to select or deselect cities.")

    def _select_all_seats(self, select):
        if self.running or self.dataset.get() != DATASETS[1] or self.romania_map is None:
            return
        self.selected_ids = {seat.id for seat in self.romania_map.seats} if select else set()
        self._selection_changed()

    def _selection_changed(self):
        # Preserve click order for the starting-city choice. Select all appends
        # new cities in dataset order and keeps any existing starting city.
        self.selection_order = [city_id for city_id in self.selection_order if city_id in self.selected_ids]
        self.selection_order.extend(seat.id for seat in self.romania_map.seats
                                    if seat.id in self.selected_ids and seat.id not in self.selection_order)
        # Stable ordering is essential: tour indices refer to this exact sequence.
        self.selected_seats = [seat for seat in self.romania_map.seats if seat.id in self.selected_ids]
        self.cities = [seat.coordinates for seat in self.selected_seats]
        start = next((seat for seat in self.selected_seats
                      if seat.id == self.selection_order[0]), None) if self.selection_order else None
        self.start_label.set(f"Start: {start.name}" if start else "Start: --")
        self._clear_result()
        self.selection_label.set(f"{len(self.cities)} / {len(self.romania_map.seats)} cities selected")
        self.start_button.configure(state="normal" if len(self.cities) >= 2 else "disabled")
        self.status.set(f"Selected {len(self.cities)} cities. Select at least two, then Start. Distances are geographic kilometers, not driving distances.")
        self._draw_map()

    def generate_cities(self):
        """Generate data only on request, independently of algorithm parameters."""
        if self.running or self.dataset.get() != DATASETS[0]:
            return
        try:
            try:
                count = int(self.fields["city_count"].get())
            except ValueError:
                raise ValueError("City count must be a whole number.") from None
            try:
                seed = int(self.fields["seed"].get())
            except ValueError:
                raise ValueError("Seed must be a whole number.") from None
            cities = generate_random_cities(count, seed)
        except ValueError as error:
            self.feedback.set(str(error))
            self.status.set("Generation failed. Previously loaded cities were kept.")
            return
        self.cities = cities
        self.loaded_seed = seed
        self._clear_result()
        self.start_button.configure(state="normal")
        self._draw_map()
        self.feedback.set(f"Loaded {count} cities. Labels are city indices, starting at 0.")
        self.status.set(f"Loaded {count} random cities with seed {seed}. Press Start to optimize.")

    def check_settings(self):
        values = {name: field.get() for name, field in self.fields.items()}
        # Geographic datasets will supply their own city count when implemented.
        if self.dataset.get() != DATASETS[0]:
            values["city_count"] = DEFAULTS["city_count"]
        try:
            read_settings(values)
        except ValueError as error:
            self.feedback.set(str(error))
            self.status.set("Please correct the settings before continuing.")
            return
        self.feedback.set("Settings are valid.")
        self.status.set("Settings checked. Start uses the selected cities." if self.dataset.get() == DATASETS[1]
                        else "Settings checked. Start uses the loaded cities; generate again to change their count.")

    def _set_running(self, running):
        self.running = running
        for widget in self.input_widgets + [self.check_button, self.reset_button]:
            widget.configure(state="disabled" if running else "normal")
        self.selector.configure(state="disabled" if running else "readonly")
        random_cities = self.dataset.get() == DATASETS[0]
        self.city_count_entry.configure(state="normal" if not running and random_cities else "disabled")
        self.generate_button.configure(state="normal" if not running and random_cities else "disabled")
        self.start_button.configure(state="normal" if not running and len(self.cities) >= 2 else "disabled")
        for widget in (self.select_all_button, self.clear_selection_button):
            widget.configure(state="disabled" if running else "normal")
        self._sync_playback_controls()

    def start_run(self):
        if self.running:
            return
        if len(self.cities) < 2:
            self.status.set("Generate or select at least two cities before starting.")
            return
        values = {name: field.get() for name, field in self.fields.items()}
        # The loaded city set is authoritative; editing the count never changes it.
        values["city_count"] = str(len(self.cities))
        try:
            _, seed, config = read_settings(values)
        except ValueError as error:
            self.feedback.set(str(error))
            self.status.set("Run not started. Please correct the settings.")
            return
        self._clear_result()
        self._draw_map()
        self._set_running(True)
        self.feedback.set(f"Running on {len(self.cities)} loaded cities with solver seed {seed}.")
        self.status.set(f"Running {config.iterations} iterations. Results will appear when the run finishes.")
        try:
            Thread(target=run_solver, args=(tuple(self.cities), config, seed, self.messages),
                   kwargs={"geographic": self.dataset.get() == DATASETS[1]},
                   daemon=True).start()
        except Exception as error:
            self._set_running(False)
            self.status.set(f"Could not start solver: {error}")
            return
        self.root.after(100, self._poll_result)

    def _poll_result(self):
        """Only the main GUI thread touches widgets, including on failure."""
        try:
            message = self.messages.get_nowait()
        except Empty:
            self.root.after(100, self._poll_result)
            return
        self._set_running(False)
        if isinstance(message, Exception):
            self.feedback.set(str(message))
            self.status.set("Solver failed. Correct the settings and try again.")
            return
        if self.dataset.get() == DATASETS[1] and self.selection_order:
            start_index = next(index for index, seat in enumerate(self.selected_seats)
                               if seat.id == self.selection_order[0])
            message = with_start_city(message, start_index)
        self.result = message
        self.best_distance.set(f"Best distance: {message.best_length:.4f} {self._distance_unit()}")
        self.slider.configure(to=len(message.history), state="normal" if len(message.history) > 1 else "disabled")
        self.iteration.set(len(message.history))
        self._select_iteration()
        self._sync_playback_controls()
        self.feedback.set("Run complete. Orange marker identifies the displayed tour's start.")
        self.status.set("Run complete. Move the slider to inspect history, or change parameters and press Start again.")
        if self.animate_iterations.get() and len(message.history) > 1:
            self.toggle_playback()

    def reset_form(self):
        if self.running:
            return
        for name, value in DEFAULTS.items():
            self.fields[name].set(value)
        self.dataset.set(DATASETS[0])
        self.animate_iterations.set(False)
        self.playback_speed.set("Normal (300 ms)")
        self._dataset_changed()
        self.best_distance.set("Best distance: --")
        self.status.set("Form reset to defaults.")


def main():
    root = tk.Tk()
    ExplorerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
