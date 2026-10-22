import pytest

from algorithm.baselines import nearest_neighbor, nearest_neighbor_distance_matrix


def test_nearest_neighbor_returns_valid_closed_tour() -> None:
    cities = [(0, 0), (1, 0), (1, 1), (0, 1)]

    tour, length = nearest_neighbor(cities)

    assert len(tour) == len(cities)
    assert set(tour) == set(range(len(cities)))
    assert length == pytest.approx(4.0)


def test_nearest_neighbor_uses_lowest_index_for_ties() -> None:
    cities = [(0, 0), (1, 0), (1, 1), (0, 1)]

    tour, _ = nearest_neighbor(cities)

    # From city 0, cities 1 and 3 are equally close. With start city 0 tried
    # first, the algorithm should break that tie by choosing city 1.
    assert tour[0] == 0
    assert tour[1] == 1


def test_nearest_neighbor_distance_matrix_supports_asymmetric_costs() -> None:
    costs = [
        [0, 1, 10],
        [10, 0, 1],
        [1, 10, 0],
    ]

    tour, length = nearest_neighbor_distance_matrix(costs)

    assert tour == [0, 1, 2]
    assert length == pytest.approx(3.0)


@pytest.mark.parametrize("cities", [[], [(0, 0)], [(0, 0), (0, 0)]])
def test_nearest_neighbor_rejects_invalid_cities(
    cities: list[tuple[int, int]],
) -> None:
    with pytest.raises(ValueError):
        nearest_neighbor(cities)
