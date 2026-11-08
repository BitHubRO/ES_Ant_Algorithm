"""Baseline algorithms for the Traveling Salesperson Problem."""

from __future__ import annotations

from collections.abc import Sequence
import random
from time import perf_counter

from .aco import IterationProgress, Result

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
    return _nearest_neighbor_with_distances(distances)


def _nearest_neighbor_with_distances(distances, cancel_check=None):
    """Construct one greedy tour per start, using an already validated matrix."""
    city_count = len(distances)
    best_tour: list[int] | None = None
    best_length = float("inf")

    for start_city in range(city_count):
        if cancel_check is not None:
            cancel_check()
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


def random_search_distance_matrix(cost_matrix, samples, seed=None, *, batch_size=1, progress_callback=None):
    """Sample complete shuffled tours and keep the best; repeated tours count."""
    return _random_search_with_distances(validate_distance_matrix(cost_matrix), samples, seed,
                                         batch_size=batch_size, progress_callback=progress_callback)


def _random_search_with_distances(distances, samples, seed=None, *, batch_size=1, progress_callback=None):
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise ValueError("samples must be a positive integer")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    started = perf_counter()
    rng = random.Random(seed)
    city_count = len(distances)
    best_tour, best_length = None, float("inf")
    history, tour_history = [], []
    batches = (samples + batch_size - 1) // batch_size
    compute_seconds = perf_counter() - started
    evaluated = 0
    for batch in range(batches):
        started = perf_counter()
        for _ in range(min(batch_size, samples - evaluated)):
            tour = list(range(city_count))
            rng.shuffle(tour)
            length = tour_length(tour, distances)
            evaluated += 1
            if length < best_length:
                best_tour, best_length = tuple(tour), length
        history.append(best_length)
        tour_history.append(best_tour)
        compute_seconds += perf_counter() - started
        if progress_callback is not None:
            progress_callback(IterationProgress(batch + 1, batches, best_tour, best_length,
                                                 compute_seconds=compute_seconds))
    return Result(best_tour, best_length, history, tour_history, compute_seconds=compute_seconds)
