"""Baseline algorithms for the Traveling Salesperson Problem."""

from __future__ import annotations

from collections.abc import Sequence

from .tsp import (
    City,
    distance_matrix,
    tour_length,
    validate_distance_matrix,
)


def nearest_neighbor(cities: Sequence[City]) -> tuple[list[int], float]:
    """Return the shortest nearest-neighbor tour across all starting cities.

    Ties between equally distant next cities are resolved by choosing the
    lowest city index.
    """
    distances = distance_matrix(cities)
    return nearest_neighbor_distance_matrix(distances)


def nearest_neighbor_distance_matrix(
    cost_matrix: Sequence[Sequence[float]],
) -> tuple[list[int], float]:
    """Return the shortest nearest-neighbor tour using a directed cost matrix."""
    distances = validate_distance_matrix(cost_matrix)
    city_count = len(distances)
    best_tour: list[int] | None = None
    best_length = float("inf")

    for start_city in range(city_count):
        tour = [start_city]
        unvisited = set(range(city_count))
        unvisited.remove(start_city)

        while unvisited:
            current_city = tour[-1]
            next_city = min(
                unvisited,
                key=lambda city: (distances[current_city][city], city),
            )
            tour.append(next_city)
            unvisited.remove(next_city)

        length = tour_length(tour, distances)
        if length < best_length:
            best_tour = tour
            best_length = length

    if best_tour is None:
        raise RuntimeError("nearest-neighbor search did not produce a tour")

    return best_tour, best_length
