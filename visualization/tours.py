"""Prepare closed tours for display without changing their edges or costs."""

from dataclasses import replace

from algorithm.aco import Result


def with_start_city(result: Result, city_index: int) -> Result:
    """Rotate the best tour and every saved tour to the requested city index.

    For example, (2, 0, 1) starting at 0 becomes (0, 1, 2). The final
    edge still wraps to the first city, so the closed tour has the same cost.
    """
    def rotate(tour):
        cities = tuple(tour)
        offset = cities.index(city_index)
        return cities[offset:] + cities[:offset]

    return replace(result, best_tour=rotate(result.best_tour),
                   tour_history=tuple(rotate(tour) for tour in result.tour_history))
