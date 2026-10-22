"""Basic distance and tour-length helpers for the Traveling Salesperson Problem."""

from __future__ import annotations

import math
from collections.abc import Sequence

City = tuple[float, float]
DistanceMatrix = list[list[float]]


def validate_distance_matrix(
    distances: Sequence[Sequence[float]],
) -> DistanceMatrix:
    """Validate and copy a complete directed cost matrix.

    Diagonal entries must be zero and every edge between different cities must
    have a positive finite cost. Positive off-diagonal costs are required by
    ACO's reciprocal-distance heuristic.
    """
    city_count = len(distances)
    if city_count < 2:
        raise ValueError("the distance matrix must contain at least two cities")

    validated: DistanceMatrix = []
    for i, row in enumerate(distances):
        if len(row) != city_count:
            raise ValueError("the distance matrix must be square")
        validated_row: list[float] = []
        for j, cost in enumerate(row):
            if (
                not isinstance(cost, (int, float))
                or isinstance(cost, bool)
                or not math.isfinite(cost)
            ):
                raise ValueError("distance matrix costs must be finite numbers")
            if i == j and cost != 0:
                raise ValueError("distance matrix diagonal entries must be zero")
            if i != j and cost <= 0:
                raise ValueError(
                    "costs between different cities must be positive"
                )
            validated_row.append(float(cost))
        validated.append(validated_row)
    return validated


"""
if there are fewer than 2 cities:
    report invalid input

for each city:
    check it has exactly 2 coordinates
    check both coordinates are finite numbers

if any two cities have identical coordinates:
    report invalid input

create an empty distance table

for each city i:
    create an empty row
    for each city j:
        dx = x coordinate of i - x coordinate of j
        dy = y coordinate of i - y coordinate of j
        distance = sqrt(dx squared + dy squared)
        add distance to the row
    add the row to the table

return the table
"""
def distance_matrix(cities: Sequence[City]) -> DistanceMatrix:
    """Return the Euclidean distance between every pair of cities.

    Cities are represented by ``(x, y)`` coordinates. The returned matrix is
    indexed with city numbers, so ``matrix[i][j]`` is the distance from city
    ``i`` to city ``j``.
    """
    if len(cities) < 2:
        raise ValueError("not enough cities to compute distances")

    for city in cities:
        if len(city) != 2:
            raise ValueError("each city must have exactly two coordinates")
        if not all(math.isfinite(coordinate) for coordinate in city):
            raise ValueError("city coordinates must be finite numbers")

    if len(set(cities)) != len(cities):
        raise ValueError("city coordinates must be distinct")

    return [
        [
            math.hypot(cities[i][0] - cities[j][0], cities[i][1] - cities[j][1])
            for j in range(len(cities))
        ]
        for i in range(len(cities))
    ]



"""
city_count = number of rows in distances

check there are at least 2 cities
check every row has city_count entries
check tour has exactly city_count entries
check every tour entry is an integer index from 0 to city_count - 1
check no city index appears more than once

total = 0
for each position k in tour:
    current = tour[k]
    next = tour[(k + 1) modulo city_count]
    total = total + distances[current][next]

return total
"""
def tour_length(tour: Sequence[int], distances: Sequence[Sequence[float]]) -> float:
    """Return the length of a closed tour through every city exactly once.

    ``tour`` contains city indices without repeating its starting city at the
    end. The distance from the last city back to the first is included.
    """
    city_count = len(distances)
    if city_count < 2:
        raise ValueError("the distance matrix must contain at least two cities")
    if any(len(row) != city_count for row in distances):
        raise ValueError("the distance matrix must be square")
    if len(tour) != city_count:
        raise ValueError("the tour must contain every city exactly once")
    if any(
        not isinstance(city, int)
        or isinstance(city, bool)
        or city < 0
        or city >= city_count
        for city in tour
    ):
        raise ValueError("tour entries must be valid city indices")
    if len(set(tour)) != city_count:
        raise ValueError("the tour must not visit a city more than once")

    total = 0.0
    for index, city in enumerate(tour):
        next_city = tour[(index + 1) % city_count]
        total += distances[city][next_city]
    return total