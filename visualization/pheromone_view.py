"""Scrollable pheromone heatmap with city-aware hover details and a legend."""

import math
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont


def pheromone_color(value, maximum, logarithmic=True):
    """Light to dark blue, normalized against a shared run maximum."""
    transform = math.log1p if logarithmic else float
    ratio = transform(max(0.0, value)) / transform(maximum) if maximum > 0 else 0.0
    ratio = min(1.0, max(0.0, ratio))
    light, dark = (241, 246, 251), (23, 59, 117)
    rgb = tuple(round(a + ratio * (b - a)) for a, b in zip(light, dark))
    return "#" + "".join(f"{channel:02x}" for channel in rgb)


def matrix_cell(x, y, count, size, left=48, top=32):
    """Translate canvas coordinates into (row, column); exclude margins."""
    row, column = math.floor((y - top) / size), math.floor((x - left) / size)
    return (row, column) if 0 <= row < count and 0 <= column < count else None


class PheromoneView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.matrix = None
        self.labels = []
        self.iteration = 0
        self.maximum = 0.0
        self.cell_size = 18
        self.logarithmic = tk.BooleanVar(value=True)
        self.detail = tk.StringVar(value="Run the solver with Record pheromone history enabled.")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Checkbutton(header, text="Log color scale: log(1 + pheromone)",
                        variable=self.logarithmic, command=self.redraw).pack(anchor="w")
        self.legend = tk.Canvas(header, width=310, height=30, highlightthickness=0)
        self.legend.pack(anchor="w")
        self.canvas = tk.Canvas(self, height=185, background="white", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(self, orient="vertical", command=self._scroll_y)
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self._scroll_x)
        horizontal.grid(row=2, column=0, sticky="ew")
        self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        # Reserve hover text space up front. Otherwise a longer message wraps
        # after a run and steals height from the matrix inside a small pane.
        details = ttk.Frame(self, height=tkfont.nametofont("TkDefaultFont").metrics("linespace") * 3)
        details.grid(row=3, column=0, columnspan=2, sticky="ew")
        details.grid_propagate(False)
        details.columnconfigure(0, weight=1)
        self.detail_label = ttk.Label(details, textvariable=self.detail, wraplength=700)
        self.detail_label.grid(row=0, column=0, sticky="nw")
        details.bind("<Configure>", lambda event: self.detail_label.configure(wraplength=max(100, event.width - 8)))
        self.canvas.bind("<Configure>", self.redraw)
        self.canvas.bind("<Map>", self.redraw)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", lambda event: self._set_summary())

    def show(self, matrix, labels=(), iteration=0, maximum=0.0):
        reset_scroll = self.matrix is None or matrix is None or len(labels) != len(self.labels)
        self.matrix, self.labels = matrix, labels
        self.iteration, self.maximum = iteration, maximum
        if reset_scroll:
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
        self._set_summary()
        # Avoid constructing thousands of cells while the cost tab is open.
        if self.canvas.winfo_ismapped():
            self.redraw()

    def _set_summary(self):
        self.detail.set(
            f"Iteration {self.iteration}: rows = from, columns = to. Hover for names and values. Scroll to see more cells."
            if self.matrix is not None else "No matrix recorded. Enable Record pheromone history before the next run.")

    def _scroll_y(self, *args):
        self.canvas.yview(*args)
        self.redraw()

    def _scroll_x(self, *args):
        self.canvas.xview(*args)
        self.redraw()

    def redraw(self, event=None):
        if not self.canvas.winfo_ismapped():
            return
        self.canvas.delete("all")
        self.legend.delete("all")
        if self.matrix is None:
            self.canvas.configure(scrollregion=(0, 0, 1, 1))
            self.canvas.create_text(20, 25, anchor="nw", text="Pheromone matrix appears after each recorded iteration.")
            return
        count = len(self.matrix)
        self.cell_size = max(16, min(28, (self.canvas.winfo_height() - 40) // count))
        size = self.cell_size
        # Draw only the viewport, even when the complete recorded matrix is large.
        col0 = max(0, math.floor((self.canvas.canvasx(0) - 48) / size))
        row0 = max(0, math.floor((self.canvas.canvasy(0) - 32) / size))
        col1 = min(count, math.ceil((self.canvas.canvasx(self.canvas.winfo_width()) - 48) / size))
        row1 = min(count, math.ceil((self.canvas.canvasy(self.canvas.winfo_height()) - 32) / size))
        for i in range(col0, col1):
            short_name = self.labels[i][0]
            self.canvas.create_text(48 + (i + 0.5) * size, 22, text=short_name, font=("Segoe UI", 8))
        for i in range(row0, row1):
            short_name = self.labels[i][0]
            self.canvas.create_text(40, 32 + (i + 0.5) * size, text=short_name, anchor="e", font=("Segoe UI", 8))
        for row in range(row0, row1):
            for column in range(col0, col1):
                value = self.matrix[row][column]
                color = "#c9cfd5" if row == column else pheromone_color(value, self.maximum, self.logarithmic.get())
                x, y = 48 + column * size, 32 + row * size
                self.canvas.create_rectangle(x, y, x + size, y + size, fill=color, outline="white", tags="matrix-cell")
        self.canvas.configure(scrollregion=(0, 0, 56 + count * size, 40 + count * size))
        for i in range(50):
            # Interpolate in the selected scale so the legend matches cell colors.
            fraction = i / 49
            value = math.expm1(fraction * math.log1p(self.maximum)) if self.logarithmic.get() else fraction * self.maximum
            self.legend.create_rectangle(5 + i * 2, 2, 7 + i * 2, 13,
                                         fill=pheromone_color(value, self.maximum, self.logarithmic.get()), outline="")
        self.legend.create_text(5, 23, anchor="w", text="0", font=("Segoe UI", 8))
        self.legend.create_text(107, 23, anchor="e", text=f"{self.maximum:.4g}", font=("Segoe UI", 8))
        self.legend.create_rectangle(125, 2, 136, 13, fill="#c9cfd5", outline="")
        self.legend.create_text(141, 8, anchor="w", text="diagonal (unused)", font=("Segoe UI", 8))

    def _hover(self, event):
        if self.matrix is None:
            return
        cell = matrix_cell(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y), len(self.matrix), self.cell_size)
        if cell is None:
            self._set_summary()
            return
        row, column = cell
        source, destination = self.labels[row][1], self.labels[column][1]
        self.detail.set(f"Iteration {self.iteration} | [{row}, {column}] {source} → {destination} | "
                        f"pheromone = {self.matrix[row][column]!r}"
                        + (" (diagonal; unused)" if row == column else ""))
