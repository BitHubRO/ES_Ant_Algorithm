"""ACO explorer window with repeatable random city generation.

Run from the repository root with ``python -m visualization.app``.
Romania county seats can be selected on an offline geographic map.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from dataclasses import asdict, replace
import math
from queue import Empty, Queue
from threading import Event, Thread

from algorithm.aco import Config, IterationProgress, Result
from algorithm.tsp import City
from algorithm.visualize_solution import scale_city_positions, scale_history
from .datasets import generate_random_cities
from .runner import run_comparison
from .romania_map import RomaniaMap
from .tours import with_start_city
from .pheromone_view import PheromoneView
from .comparison_plot import draw_comparison_plot
from algorithm.comparison import METHODS, METHOD_NAMES, METHOD_COLORS, MethodReport, ComparisonEvent, ComparisonFinished
from algorithm.comparison_export import comparison_rows, write_comparison_csv


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
        root.minsize(1100, 760)
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
        self.comparison_reports = {}
        self.method_states = {method: "Waiting" for method in METHODS}
        self.random_history, self.random_tours = [], []
        self.run_ants, self.run_budget = 0, 0
        self.run_metadata = None
        self.route_method = tk.StringVar(value=METHOD_NAMES["aco"])
        self.route_info = tk.StringVar(value="No route available")
        self.comparison_summary = tk.StringVar(value="All three methods use the same cities and costs.")
        self.running = False
        self.slow_live = tk.BooleanVar(value=False)
        self.live_speed = tk.StringVar(value="Normal (300 ms)")
        self.run_total = 0
        self.live_history = []
        self.live_tours = []
        self.live_pheromones = []
        self.pheromone_max = 0.0
        self.record_pheromones = tk.BooleanVar(value=True)
        self.cancel_event = Event()
        self.playing = False
        self.animation_after = None
        self.animate_iterations = tk.BooleanVar(value=False)
        self.playback_speed = tk.StringVar(value="Normal (300 ms)")
        self.messages: Queue[Result | IterationProgress | Exception] = Queue()
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
        self.start_button = ttk.Button(actions, text="Run all 3", command=self.start_run, state="disabled")
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
        self.live_checkbox = ttk.Checkbutton(
            controls, text="Slow live run", variable=self.slow_live,
            command=self._live_option_changed)
        self.live_checkbox.grid(row=16, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.live_speed_selector = ttk.Combobox(
            controls, textvariable=self.live_speed, values=tuple(PLAYBACK_SPEEDS),
            state="disabled", width=21)
        self.live_speed_selector.grid(row=17, column=0, columnspan=2, sticky="ew")

    def _build_display(self, parent):
        # Give map and analysis the full available height. Stacking them let
        # the map hide the plots when the horizontal divider moved too far.
        self.display_split = tk.PanedWindow(
            parent, orient=tk.HORIZONTAL, sashwidth=8, sashrelief=tk.RAISED,
            showhandle=True, background="#cbd3db", borderwidth=0,
            sashcursor="sb_h_double_arrow")
        self.display_split.grid(row=2, column=1, rowspan=2, sticky="nsew")
        self._split_initialized = False
        self.display_split.bind("<Configure>", self._initialize_split)
        map_frame = ttk.LabelFrame(self.display_split, text="City map", padding=8)
        self.map_frame = map_frame
        self.display_split.add(map_frame, minsize=300, stretch="always")
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
        ttk.Label(map_frame, textvariable=self.map_hint, wraplength=350).grid(row=2, column=0, sticky="w", pady=(3, 0))
        self.attribution = ttk.Label(map_frame, text="Boundaries: geoBoundaries / World Bank (CC BY 4.0). Cities: GeoNames / Călărași council.",
                                     font=("Segoe UI", 8), wraplength=350)
        self.attribution.grid(row=3, column=0, sticky="w")
        self.attribution.grid_remove()
        route_bar = ttk.Frame(map_frame)
        route_bar.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(route_bar, text="Show route:").pack(side="left", padx=(0, 6))
        self.route_selector = ttk.Combobox(route_bar, textvariable=self.route_method,
                                          values=tuple(METHOD_NAMES.values()), state="readonly", width=18)
        self.route_selector.pack(side="left")
        self.route_selector.bind("<<ComboboxSelected>>", self._route_changed)

        results = ttk.LabelFrame(self.display_split, text="Results", padding=10)
        self.results_frame = results
        self.display_split.add(results, minsize=420, stretch="always")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        summary = ttk.Frame(results)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)
        self.export_button = ttk.Button(summary, text="Export CSV", command=self.export_comparison, state="disabled")
        self.export_button.grid(row=0, column=0, sticky="e", pady=(0, 4))
        self.comparison_table = ttk.Treeview(summary, columns=("method", "cost", "time", "tours", "state"),
                                            show="headings", height=3, selectmode="browse")
        self.comparison_table.grid(row=1, column=0, sticky="ew")
        for key, title, width in (("method", "Algorithm", 120), ("cost", "Cost", 70), ("time", "Time (s)", 65),
                                  ("tours", "Tours", 55), ("state", "Status", 65)):
            self.comparison_table.heading(key, text=title)
            self.comparison_table.column(key, width=width, minwidth=40, stretch=True,
                                          anchor="w" if key in ("method", "state") else "e")
        for method in METHODS:
            self.comparison_table.insert("", "end", iid=method,
                                         values=(METHOD_NAMES[method], "—", "—", "—", "Waiting"), tags=(method,))
            self.comparison_table.tag_configure(method, foreground=METHOD_COLORS[method])
        self.comparison_table.tag_configure("winner", background="#e3f3e8")
        self.comparison_table.bind("<<TreeviewSelect>>", self._comparison_row_selected)
        ttk.Label(summary, textvariable=self.comparison_summary, wraplength=400).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.result_tabs = ttk.Notebook(results, height=230)
        self.result_tabs.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        cost_tab = ttk.Frame(self.result_tabs)
        cost_tab.columnconfigure(0, weight=1)
        cost_tab.rowconfigure(0, weight=1)
        self.result_tabs.add(cost_tab, text="Cost evolution")
        self.chart = tk.Canvas(cost_tab, height=140, background="white", highlightthickness=0)
        self.chart.grid(row=0, column=0, sticky="nsew")
        self.chart.bind("<Configure>", self._draw_chart)
        self.chart.bind("<Map>", self._draw_chart)
        pheromone_tab = ttk.Frame(self.result_tabs)
        self.pheromone_tab = pheromone_tab
        pheromone_tab.columnconfigure(0, weight=1)
        pheromone_tab.rowconfigure(1, weight=1)
        self.result_tabs.add(pheromone_tab, text="ACO pheromones")
        self.record_checkbox = ttk.Checkbutton(
            pheromone_tab, text="Record pheromone history for the next run", variable=self.record_pheromones)
        self.record_checkbox.grid(row=0, column=0, sticky="w")
        self.pheromone_view = PheromoneView(pheromone_tab)
        self.pheromone_view.grid(row=1, column=0, sticky="nsew")
        ttk.Label(results, textvariable=self.iteration_label, wraplength=400).grid(
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
        self.speed_selector.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        route_tab = ttk.Frame(self.result_tabs)
        route_tab.columnconfigure(0, weight=1)
        route_tab.rowconfigure(1, weight=1)
        self.result_tabs.add(route_tab, text="Route details")
        ttk.Label(route_tab, textvariable=self.route_info, wraplength=400).grid(row=0, column=0, sticky="w", pady=6)
        self.route_text = tk.Text(route_tab, height=2, wrap="word", state="disabled",
                                  font=("Segoe UI", 9), relief="flat")
        self.route_text.grid(row=1, column=0, sticky="nsew")
        route_scroll = ttk.Scrollbar(route_tab, orient="vertical", command=self.route_text.yview)
        route_scroll.grid(row=1, column=1, sticky="ns")
        self.route_text.configure(yscrollcommand=route_scroll.set)

    def _initialize_split(self, event):
        """Choose the initial widths once, preserving later user adjustments."""
        if not self._split_initialized and event.width >= 728:
            self.display_split.sash_place(0, max(300, min(int(event.width * 0.5), event.width - 428)), 0)
            self._split_initialized = True

    def _draw_map(self, event=None):
        """Redraw from stored coordinates; resizing never regenerates cities."""
        self.map_canvas.delete("all")
        width, height = self.map_canvas.winfo_width(), self.map_canvas.winfo_height()
        tour = self._map_tour()
        route_color = METHOD_COLORS[self._active_method()]
        if self.dataset.get() == DATASETS[1] and self.romania_map is not None:
            tour_ids = ()
            if tour:
                tour_ids = tuple(self.selected_seats[i].id
                                 for i in tour)
            start_id = self.selection_order[0] if self.selection_order else None
            self.romania_map.draw(self.map_canvas, self.selected_ids, tour_ids, start_id=start_id, route_color=route_color)
            return
        if self.cities:
            # Tkinter may briefly report a tiny canvas while laying out widgets.
            if width <= 80 or height <= 80:
                return
            positions = scale_city_positions(self.cities, width, height)
            start_city = None
            if tour:
                start_city = tour[0]
                for index, city in enumerate(tour):
                    next_city = tour[(index + 1) % len(tour)]
                    self.map_canvas.create_line(
                        *positions[city], *positions[next_city],
                        fill=route_color, width=2, arrow=tk.LAST, tags="route-edge")
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
        if self.comparison_reports:
            cursor = (self._iteration_index() + 1) * self.run_ants if self.result is not None else None
            draw_comparison_plot(self.chart, self.comparison_reports, self.run_budget, cursor)
            return
        self.chart.delete("all")
        width, height = self.chart.winfo_width(), self.chart.winfo_height()
        if self.result and width > 60 and height > 35:
            padding = min(45, max(8, (height - 40) // 2), (width - 30) // 2)
            points = scale_history(self.result.history, width, height, padding=padding)
            # Keep the live x axis fixed at the requested iteration count:
            # early points occupy the left of the graph, not its full width.
            total = self.run_total if self.running else len(self.result.history)
            points = [(padding + i * (width - 2 * padding) / (total - 1) if total > 1 else width / 2, y)
                      for i, (_, y) in enumerate(points)]
            self.chart.create_line(45, 20, 45, height - 35, width - 20, height - 35,
                                   fill="#657589")
            self.chart.create_text(width / 2, height - 12, text="Iteration", fill="#44576b")
            self.chart.create_text(45, height - 25, text="1", fill="#657589")
            self.chart.create_text(width - 45, height - 25, text=str(total), fill="#657589")
            self.chart.create_text(12, height / 2, text="Distance", angle=90, fill="#44576b")
            self.chart.create_text(48, 12, anchor="nw",
                                   text=f"Best-so-far: {self.result.history[0]:.4f} → {self.result.best_length:.4f}")
            if len(points) > 1:
                self.chart.create_line(*[value for point in points for value in point],
                                       fill="#3274a1", width=2, tags="cost-curve")
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

    def _active_method(self):
        return next((method for method in METHODS if METHOD_NAMES[method] == self.route_method.get()), "aco")

    def _map_tour(self):
        method = self._active_method()
        report = self.comparison_reports.get(method)
        result = self.result if method == "aco" else report.result if report is not None else None
        if result is None:
            return ()
        if method == "nearest_neighbor":
            return tuple(result.best_tour)
        index = self._iteration_index() if self.result is not None else len(result.history) - 1
        return tuple(result.tour_history[min(index, len(result.tour_history) - 1)])

    def _update_route_text(self):
        tour = self._map_tour()
        if not tour:
            self._set_route_text("")
            self.route_info.set(f"{METHOD_NAMES[self._active_method()]}: waiting for a route.")
            return
        names = ([self.selected_seats[i].name for i in tour] if self.dataset.get() == DATASETS[1]
                 else [str(i) for i in tour])
        self._set_route_text(" → ".join(names + names[:1]))
        self.route_info.set(f"{METHOD_NAMES[self._active_method()]} | closed visiting order; "
                            "the slider follows ACO checkpoints. Nearest neighbor shows its final route.")

    def _route_changed(self, event=None):
        self._pause_animation()
        self._update_route_text()
        self._draw_map()

    def _comparison_row_selected(self, event=None):
        selected = self.comparison_table.selection()
        if selected:
            self.route_method.set(METHOD_NAMES[selected[0]])
            self._route_changed()

    def _refresh_comparison_table(self):
        complete = all(self.method_states[method] == "Finished" for method in METHODS)
        lowest = min((report.result.best_length for report in self.comparison_reports.values()), default=None)
        winners = []
        for method in METHODS:
            report = self.comparison_reports.get(method)
            winner = complete and report is not None and math.isclose(report.result.best_length, lowest, rel_tol=1e-9)
            if winner:
                winners.append(METHOD_NAMES[method])
            values = ((METHOD_NAMES[method], f"{report.result.best_length:.4f}",
                       f"{report.result.compute_seconds:.4g}", report.evaluations, self.method_states[method])
                      if report is not None else (METHOD_NAMES[method], "—", "—", "—", self.method_states[method]))
            self.comparison_table.item(method, values=values, tags=(method, "winner") if winner else (method,))
        if complete:
            aco_cost = self.comparison_reports["aco"].result.best_length
            nn_cost = self.comparison_reports["nearest_neighbor"].result.best_length
            percent = (nn_cost - aco_cost) / nn_cost * 100
            self.comparison_summary.set(f"Lowest cost: {', '.join(winners)}. ACO vs NN: {percent:+.2f}% improvement.")
        else:
            self.comparison_summary.set("Same costs; matched ACO/random tour budgets. Time excludes animation and drawing.")

    def export_comparison(self):
        if (self.running or len(self.comparison_reports) != 3 or self.run_metadata is None
                or not all(state == "Finished" for state in self.method_states.values())):
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Export algorithm comparison",
                                           defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                write_comparison_csv(path, comparison_rows(self.comparison_reports, self.run_metadata))
            except OSError as error:
                self.status.set(f"Could not save comparison: {error}")
                return
            self.status.set(f"Saved costs, compute times, histories, and reproducibility metadata to {path}")

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
        total = self.run_total if self.running else len(self.result.history)
        self.iteration_label.set(
            f"Iteration {index + 1}/{total} | "
            f"best-so-far distance: {self.result.history[index]:.4f} {self._distance_unit()}")
        self._update_route_text()
        self._draw_map()
        self._draw_chart()
        self._draw_pheromones()

    def _draw_pheromones(self):
        if self.result is None or not self.result.pheromone_history:
            self.pheromone_view.show(None)
            return
        index = self._iteration_index()
        labels = ([(seat.id, seat.name) for seat in self.selected_seats]
                  if self.dataset.get() == DATASETS[1]
                  else [(str(i), f"City {i}") for i in range(len(self.cities))])
        self.pheromone_view.show(self.result.pheromone_history[index], labels, index + 1, self.pheromone_max)

    def _clear_result(self):
        self._pause_animation()
        self.result = None
        self.comparison_reports = {}
        self.method_states = {method: "Waiting" for method in METHODS}
        self.random_history, self.random_tours = [], []
        self.run_metadata = None
        self.route_method.set(METHOD_NAMES["aco"])
        self.comparison_table.selection_set("aco")
        self.export_button.configure(state="disabled")
        self._refresh_comparison_table()
        self.route_info.set("No route available")
        self.live_history = []
        self.live_tours = []
        self.live_pheromones = []
        self.pheromone_max = 0.0
        self.best_distance.set("Best distance: --")
        self.slider.configure(state="disabled", to=1)
        self.iteration.set(1)
        self.iteration_label.set("No run selected")
        self._set_route_text("")
        self._draw_chart()
        self._draw_pheromones()
        self._sync_playback_controls()

    def _sync_playback_controls(self):
        enabled = self.animate_iterations.get()
        can_play = enabled and not self.running and self.result is not None and len(self.result.history) > 1
        self.play_button.configure(state="normal" if can_play else "disabled",
                                   text="Pause" if self.playing else "Play")
        self.speed_selector.configure(state="readonly" if enabled else "disabled")
        if enabled:
            self.speed_selector.grid()
        else:
            self.speed_selector.grid_remove()

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
        self.cancel_event.set()
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
        self.live_checkbox.configure(state="disabled" if running else "normal")
        self.record_checkbox.configure(state="disabled" if running else "normal")
        self._live_option_changed()
        self._sync_playback_controls()

    def _live_option_changed(self):
        self.live_speed_selector.configure(
            state="readonly" if self.slow_live.get() and not self.running else "disabled")

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
        if self.record_pheromones.get() and config.iterations * len(self.cities) ** 2 > 5_000_000:
            self.feedback.set("Pheromone history is too large. Reduce cities/iterations, or uncheck recording in the Pheromone matrix tab.")
            return
        self._clear_result()
        self.run_total = config.iterations
        self.run_ants = config.ants or len(self.cities)
        self.run_budget = self.run_ants * config.iterations
        self.run_metadata = dict(seed=seed, dataset=self.dataset.get(), unit=self._distance_unit(),
                                 city_count=len(self.cities), config=asdict(config),
                                 start_city=self.selected_seats[next(i for i, seat in enumerate(self.selected_seats)
                                            if seat.id == self.selection_order[0])].name if self.selection_order else "",
                                 cities=[dict(name=self.selected_seats[i].name if self.selected_seats else f"City {i}",
                                              coordinates=city) for i, city in enumerate(self.cities)])
        self.comparison_table.heading("cost", text="Cost (km)" if self.dataset.get() == DATASETS[1] else "Cost")
        self.cancel_event = Event()
        self.slider.configure(to=config.iterations, state="disabled")
        self._draw_map()
        self._set_running(True)
        self.feedback.set(f"Running on {len(self.cities)} loaded cities with solver seed {seed}.")
        self.status.set(f"Running {config.iterations} iterations. " + (
            "The cost line and best route update after each iteration." if self.slow_live.get()
            else "Results will appear when the run finishes."))
        try:
            Thread(target=run_comparison, args=(tuple(self.cities), config, seed, self.messages),
                   kwargs={"geographic": self.dataset.get() == DATASETS[1],
                           "live_updates": self.slow_live.get(),
                           "iteration_delay": PLAYBACK_SPEEDS[self.live_speed.get()] / 1000 if self.slow_live.get() else 0.0,
                           "cancel_event": self.cancel_event,
                           "record_pheromones": self.record_pheromones.get()},
                   # Matrix recording is optional for experiments and larger runs.
                   daemon=True).start()
        except Exception as error:
            self._set_running(False)
            self.status.set(f"Could not start solver: {error}")
            return
        self.root.after(30, self._poll_result)

    def _with_selected_start(self, result):
        if self.dataset.get() == DATASETS[1] and self.selection_order:
            start_index = next(index for index, seat in enumerate(self.selected_seats)
                               if seat.id == self.selection_order[0])
            return with_start_city(result, start_index)
        return result

    def _show_progress(self, progress):
        snapshot = self._with_selected_start(Result(
            progress.best_tour, progress.best_length, [progress.best_length], [progress.best_tour]))
        self.live_history.append(progress.best_length)
        self.live_tours.append(snapshot.best_tour)
        if progress.pheromones is not None:
            self.live_pheromones.append(progress.pheromones)
            self.pheromone_max = max(self.pheromone_max, max(max(row) for row in progress.pheromones))
        self.result = Result(snapshot.best_tour, snapshot.best_length, self.live_history, self.live_tours,
                             self.live_pheromones, compute_seconds=progress.compute_seconds)
        self.iteration.set(progress.iteration)
        self.best_distance.set(f"Best distance so far: {progress.best_length:.4f} {self._distance_unit()}")
        self.status.set(f"Running iteration {progress.iteration}/{progress.total_iterations} — live cost evolution.")
        self._select_iteration()

    def _handle_comparison_event(self, event):
        method = event.method
        if event.state == "running":
            self.method_states[method] = "Running"
            self.status.set(f"Running {METHOD_NAMES[method]}…")
        elif event.state == "finished":
            self.method_states[method] = "Finished"
            self.comparison_reports[method] = replace(event.report, result=self._with_selected_start(event.report.result))
            if method == "aco":
                self.result = self.comparison_reports[method].result
                self.pheromone_max = max((max(row) for matrix in self.result.pheromone_history for row in matrix), default=0.0)
                self.iteration.set(len(self.result.history))
        elif event.progress is not None:
            progress = event.progress
            if method == "aco":
                self._show_progress(progress)
                result = self.result
            else:
                snapshot = self._with_selected_start(Result(progress.best_tour, progress.best_length,
                                                             [progress.best_length], [progress.best_tour]))
                self.random_history.append(progress.best_length)
                self.random_tours.append(snapshot.best_tour)
                result = Result(snapshot.best_tour, progress.best_length, self.random_history, self.random_tours,
                                compute_seconds=progress.compute_seconds)
                self.status.set(f"Random search: batch {progress.iteration}/{progress.total_iterations}")
            # Partial reports let the common plot grow during slow computation.
            self.comparison_reports[method] = MethodReport(
                method, result, progress.iteration * self.run_ants,
                tuple(self.run_ants * (i + 1) for i in range(len(result.history))))
        self._refresh_comparison_table()
        self._update_route_text()
        self._draw_map()
        self._draw_chart()
        self._draw_pheromones()

    def _poll_result(self):
        """Only the main GUI thread touches widgets, including on failure."""
        try:
            message = self.messages.get_nowait()
        except Empty:
            self.root.after(30, self._poll_result)
            return
        if isinstance(message, ComparisonEvent):
            self._handle_comparison_event(message)
            self.root.after(30, self._poll_result)
            return
        if isinstance(message, ComparisonFinished):
            self.comparison_reports = {method: replace(report, result=self._with_selected_start(report.result))
                                       for method, report in message.reports.items()}
            self.method_states = {method: "Finished" for method in METHODS}
            self._refresh_comparison_table()
            self.export_button.configure(state="normal")
            message = self.comparison_reports["aco"].result
        if isinstance(message, IterationProgress):
            self._show_progress(message)
            self.root.after(30, self._poll_result)
            return
        self._set_running(False)
        if isinstance(message, Exception):
            self.method_states = {method: "Failed" if state == "Running" else state
                                  for method, state in self.method_states.items()}
            self._refresh_comparison_table()
            self.export_button.configure(state="disabled")
            self.feedback.set(str(message))
            self.status.set("Solver failed. Correct the settings and try again.")
            return
        message = self._with_selected_start(message)
        self.result = message
        self.pheromone_max = max((max(row) for matrix in message.pheromone_history for row in matrix), default=0.0)
        self.best_distance.set(f"Best distance: {message.best_length:.4f} {self._distance_unit()}")
        self.slider.configure(to=len(message.history), state="normal" if len(message.history) > 1 else "disabled")
        self.iteration.set(len(message.history))
        self._select_iteration()
        self._sync_playback_controls()
        self.feedback.set("Run complete. Orange marker identifies the displayed tour's start.")
        self.status.set("Run complete. Move the slider to inspect history, or change parameters and press Start again.")
        if self.comparison_reports:
            self.status.set("Comparison complete. Select a row to inspect its route; Export CSV saves all three results and histories.")
        if self.animate_iterations.get() and len(message.history) > 1:
            self.toggle_playback()

    def reset_form(self):
        if self.running:
            return
        for name, value in DEFAULTS.items():
            self.fields[name].set(value)
        self.dataset.set(DATASETS[0])
        self.animate_iterations.set(False)
        self.slow_live.set(False)
        self.record_pheromones.set(True)
        self.live_speed.set("Normal (300 ms)")
        self._live_option_changed()
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
