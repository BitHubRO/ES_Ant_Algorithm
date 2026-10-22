"""Open a small Tkinter window to inspect one ACO solution."""

from __future__ import annotations

import argparse
import math
import random
from collections.abc import Sequence

from .aco import Config, solve, solve_distance_matrix
from .road_demo import (
    CLUJ_STOPS,
    fetch_osrm_distance_matrix,
    fetch_tour_geometries,
    osrm_attribution,
)
from .tsp import City, distance_matrix


def make_demo_road_cost_matrix(cities: Sequence[City]) -> list[list[float]]:
    """Create deterministic directed costs for demonstrating matrix-based ACO.

    The costs are Euclidean distances multiplied by index-based detour factors.
    They are synthetic and are not real road distances or route geometry.
    """
    straight_line = distance_matrix(cities)
    city_count = len(cities)
    costs = [[0.0] * city_count for _ in range(city_count)]

    for start in range(city_count):
        for end in range(city_count):
            if start == end:
                continue
            detour_factor = 1.0 + ((start * 7 + end * 3) % 9) / 10
            costs[start][end] = straight_line[start][end] * detour_factor
    return costs


def scale_city_positions(
    cities: Sequence[City],
    width: int,
    height: int,
    padding: int = 40,
) -> list[tuple[float, float]]:
    """Map city coordinates to canvas positions while preserving proportions."""
    if not cities:
        raise ValueError("at least one city is required")
    if width <= 2 * padding or height <= 2 * padding:
        raise ValueError("canvas dimensions must be larger than its padding")

    min_x = min(x for x, _ in cities)
    max_x = max(x for x, _ in cities)
    min_y = min(y for _, y in cities)
    max_y = max(y for _, y in cities)
    span_x = max_x - min_x
    span_y = max_y - min_y
    drawable_width = width - 2 * padding
    drawable_height = height - 2 * padding
    scale = min(
        drawable_width / span_x if span_x else float("inf"),
        drawable_height / span_y if span_y else float("inf"),
    )
    if scale == float("inf"):
        scale = 1.0

    drawn_width = span_x * scale
    drawn_height = span_y * scale
    offset_x = (width - drawn_width) / 2
    offset_y = (height - drawn_height) / 2
    return [
        (
            offset_x + (x - min_x) * scale,
            height - offset_y - (y - min_y) * scale,
        )
        for x, y in cities
    ]


def scale_history(
    history: Sequence[float],
    width: int,
    height: int,
    padding: int = 45,
) -> list[tuple[float, float]]:
    """Map best-distance history values to points inside a chart area."""
    if not history:
        raise ValueError("history must contain at least one value")
    if width <= 2 * padding or height <= 2 * padding:
        raise ValueError("chart dimensions must be larger than its padding")
    if not all(math.isfinite(value) for value in history):
        raise ValueError("history values must be finite")

    drawable_width = width - 2 * padding
    drawable_height = height - 2 * padding
    minimum = min(history)
    maximum = max(history)
    value_range = maximum - minimum

    points: list[tuple[float, float]] = []
    for index, value in enumerate(history):
        x = (
            width / 2
            if len(history) == 1
            else padding + index * drawable_width / (len(history) - 1)
        )
        y = (
            height / 2
            if value_range == 0
            else height - padding - (value - minimum) * drawable_height / value_range
        )
        points.append((x, y))
    return points


def show_tour(
    cities: Sequence[City],
    history: Sequence[float],
    tour_history: Sequence[Sequence[int]],
    cost_matrix: Sequence[Sequence[float]] | None = None,
    cost_label: str = "distance",
    route_geometries: dict[tuple[int, ...], Sequence[City]] | None = None,
    stop_labels: Sequence[str] | None = None,
    attribution: str | None = None,
) -> None:
    """Show best-tour evolution with a slider for matching routes and lengths."""
    import tkinter as tk

    if not history or len(history) != len(tour_history):
        raise ValueError("history and tour_history must have the same nonzero length")

    route_width, route_height = 800, 450
    chart_width, chart_height = 800, 260
    all_geometry_points = [
        point
        for geometry in (route_geometries or {}).values()
        for point in geometry
    ]
    all_map_points = [*cities, *all_geometry_points]
    scaled_points = scale_city_positions(all_map_points, route_width, route_height)
    positions = scaled_points[: len(cities)]
    geometry_positions = dict(zip(all_map_points, scaled_points))
    history_points = scale_history(history, chart_width, chart_height)

    root = tk.Tk()
    root.title("ACO best-tour evolution")
    route_canvas = tk.Canvas(
        root, width=route_width, height=route_height, background="white"
    )
    route_canvas.pack()
    if attribution:
        route_canvas.create_text(
            10,
            route_height - 10,
            text=attribution,
            anchor=tk.SW,
            fill="#333333",
        )
    if cost_matrix is not None:
        route_canvas.create_text(
            route_width / 2,
            16,
            text="Synthetic directed matrix costs; lines are schematic, not roads",
            fill="#8b2f2f",
        )

    radius = 6
    for index, (x, y) in enumerate(positions):
        route_canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#e1812c",
            outline="",
            tags="city-marker",
        )
        route_canvas.create_text(
            x + 12,
            y - 12,
            text=stop_labels[index] if stop_labels else str(index),
            anchor=tk.CENTER,
            tags="city-label",
        )

    selection_label = tk.StringVar()
    tk.Label(root, textvariable=selection_label).pack()

    chart = tk.Canvas(
        root, width=chart_width, height=chart_height, background="white"
    )
    chart.pack()
    padding = 45
    chart.create_line(
        padding,
        padding,
        padding,
        chart_height - padding,
        fill="#555555",
    )
    chart.create_line(
        padding,
        chart_height - padding,
        chart_width - padding,
        chart_height - padding,
        fill="#555555",
    )
    chart.create_text(
        chart_width / 2,
        18,
        text="Best tour length by iteration",
        fill="#222222",
    )
    chart.create_text(
        chart_width / 2,
        chart_height - 12,
        text=f"Iteration (1 to {len(history)})",
        fill="#222222",
    )
    chart.create_text(
        16,
        chart_height / 2,
        text="Distance",
        angle=90,
        fill="#222222",
    )
    for first, second in zip(history_points, history_points[1:]):
        chart.create_line(
            first[0],
            first[1],
            second[0],
            second[1],
            fill="#3274a1",
            width=2,
        )

    cursor = chart.create_line(
        0,
        padding,
        0,
        chart_height - padding,
        fill="#e1812c",
        dash=(4, 3),
    )
    marker = chart.create_oval(0, 0, 0, 0, fill="#e1812c", outline="")

    def display_iteration(value: str) -> None:
        index = max(0, min(len(history) - 1, int(round(float(value))) - 1))
        selected_tour = tour_history[index]
        selected_length = history[index]

        route_canvas.delete("route-edge")
        geometry = (route_geometries or {}).get(tuple(selected_tour))
        if geometry:
            line_points = [
                coordinate
                for point in geometry
                for coordinate in geometry_positions[point]
            ]
            route_canvas.create_line(
                *line_points,
                fill="#3274a1",
                width=2,
                arrow=tk.LAST,
                tags="route-edge",
            )
        else:
            for edge_index, city in enumerate(selected_tour):
                next_city = selected_tour[(edge_index + 1) % len(selected_tour)]
                start_x, start_y = positions[city]
                end_x, end_y = positions[next_city]
                route_canvas.create_line(
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    fill="#3274a1",
                    width=2,
                    arrow=tk.LAST,
                    tags="route-edge",
                )
        if cost_matrix is not None and not geometry:
            for edge_index, city in enumerate(selected_tour):
                next_city = selected_tour[(edge_index + 1) % len(selected_tour)]
                start_x, start_y = positions[city]
                end_x, end_y = positions[next_city]
                route_canvas.create_text(
                    (start_x + end_x) / 2,
                    (start_y + end_y) / 2,
                    text=f"{cost_matrix[city][next_city]:.0f}",
                    fill="#222222",
                    font=("TkDefaultFont", 8),
                    tags="route-edge",
                )
        route_canvas.tag_raise("city-marker")
        route_canvas.tag_raise("city-label")

        point_x, point_y = history_points[index]
        chart.coords(cursor, point_x, padding, point_x, chart_height - padding)
        chart.coords(
            marker,
            point_x - 4,
            point_y - 4,
            point_x + 4,
            point_y + 4,
        )
        selection_label.set(
            f"Iteration {index + 1}/{len(history)} — best {cost_label}: {selected_length:.4f}"
        )

    slider = tk.Scale(
        root,
        from_=1,
        to=len(history),
        orient=tk.HORIZONTAL,
        showvalue=False,
        resolution=1,
        command=display_iteration,
        label="Iteration",
        length=chart_width - 2 * padding,
    )
    slider.pack()
    slider.set(len(history))
    display_iteration(str(len(history)))

    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run ACO once and display its best TSP tour."
    )
    parser.add_argument("--cities", type=int, default=20, help="number of cities")
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="number of ACO iterations (default: 100, or 8 for Cluj road demo)",
    )
    parser.add_argument("--seed", type=int, default=7, help="random seed")
    parser.add_argument(
        "--cost-mode",
        choices=("euclidean", "matrix-demo", "cluj-road"),
        default="euclidean",
        help="Euclidean, synthetic directed costs, or live Cluj road routes",
    )
    args = parser.parse_args()
    iterations = args.iterations
    if iterations is None:
        iterations = 8 if args.cost_mode == "cluj-road" else 100

    if args.cities < 2:
        parser.error("--cities must be at least 2")
    if iterations < 1:
        parser.error("--iterations must be at least 1")
    if args.cost_mode == "cluj-road" and iterations > 12:
        parser.error(
            "cluj-road mode is limited to 12 iterations to limit public demo-server requests"
        )

    route_geometries = None
    stop_labels = None
    attribution = None
    rng = random.Random(args.seed)
    config = Config(ants=args.cities, iterations=iterations)
    cost_matrix = None
    cost_label = "distance"
    if args.cost_mode == "cluj-road":
        stop_labels = [name for name, _ in CLUJ_STOPS]
        cities = [coordinates for _, coordinates in CLUJ_STOPS]
        try:
            print("Fetching Cluj driving-distance matrix from the public OSRM demo server...")
            cost_matrix = fetch_osrm_distance_matrix(CLUJ_STOPS)
            config = Config(ants=len(cities), iterations=iterations)
            result = solve_distance_matrix(cost_matrix, config, seed=args.seed)
            print("Fetching road geometry for distinct best-tour snapshots...")
            route_geometries = fetch_tour_geometries(
                CLUJ_STOPS, result.tour_history
            )
        except RuntimeError as error:
            parser.error(f"Cluj road demo failed: {error}")
        cost_label = "road distance (m)"
        attribution = osrm_attribution()
    else:
        cities = []
        seen: set[City] = set()
        while len(cities) < args.cities:
            city = (rng.random(), rng.random())
            if city not in seen:
                cities.append(city)
                seen.add(city)

    if args.cost_mode == "matrix-demo":
        cost_matrix = make_demo_road_cost_matrix(cities)
        result = solve_distance_matrix(cost_matrix, config, seed=args.seed)
        cost_label = "matrix cost"
    elif args.cost_mode == "euclidean":
        result = solve(cities, config, seed=args.seed)
    print(f"Best tour length: {result.best_length:.4f}")
    print(f"Tour: {' -> '.join(map(str, result.best_tour))}")
    if cost_matrix is not None:
        print("Matrix costs are synthetic; the map lines are schematic, not roads.")
    show_tour(
        cities,
        result.history,
        result.tour_history,
        cost_matrix=cost_matrix,
        cost_label=cost_label,
        route_geometries=route_geometries,
        stop_labels=stop_labels,
        attribution=attribution,
    )


if __name__ == "__main__":
    main()
