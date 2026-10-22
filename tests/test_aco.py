import random

import pytest

from algorithm.aco import (
    Config,
    build_tour,
    choose_next_city,
    solve,
    solve_distance_matrix,
    update_pheromones,
)
from algorithm.tsp import distance_matrix, tour_length


def make_pheromones(city_count: int) -> list[list[float]]:
    return [
        [1.0 if i != j else 0.0 for j in range(city_count)]
        for i in range(city_count)
    ]


def test_choose_next_city_returns_unvisited_candidate() -> None:
    cities = [(0, 0), (1, 0), (0, 1)]
    distances = distance_matrix(cities)
    pheromones = make_pheromones(len(cities))
    current = 0
    unvisited = [1, 2]
    rng = random.Random(42)

    chosen = choose_next_city(
        current, unvisited, pheromones, distances, Config(), rng
    )

    assert chosen in unvisited
    assert chosen != current
    assert choose_next_city(
        current, [2], pheromones, distances, Config(), rng
    ) == 2


def test_build_tour_visits_every_city_once() -> None:
    cities = [(0, 0), (1, 0), (0, 1), (1, 1)]
    distances = distance_matrix(cities)
    pheromones = make_pheromones(len(cities))

    tour = build_tour(
        len(cities), pheromones, distances, Config(), random.Random(42)
    )

    assert len(tour) == len(cities)
    assert set(tour) == set(range(len(cities)))
    assert len(set(tour)) == len(cities)


def test_update_pheromones_evaporates_and_deposits_correctly() -> None:
    city_count = 4
    pheromones = make_pheromones(city_count)
    config = Config(rho=0.5, q=8)
    tours_with_lengths = [([0, 1, 2, 3], 4)]

    update_pheromones(pheromones, tours_with_lengths, config)

    expected = [
        [0.0, 2.5, 0.5, 2.5],
        [2.5, 0.0, 2.5, 0.5],
        [0.5, 2.5, 0.0, 2.5],
        [2.5, 0.5, 2.5, 0.0],
    ]
    for actual_row, expected_row in zip(pheromones, expected):
        assert actual_row == pytest.approx(expected_row)


def test_update_pheromones_can_preserve_directed_edges() -> None:
    pheromones = make_pheromones(4)

    update_pheromones(
        pheromones,
        [([0, 1, 2, 3], 4)],
        Config(rho=0.5, q=8),
        symmetric=False,
    )

    assert pheromones[0] == pytest.approx([0.0, 2.5, 0.5, 0.5])
    assert pheromones[1] == pytest.approx([0.5, 0.0, 2.5, 0.5])
    assert pheromones[2] == pytest.approx([0.5, 0.5, 0.0, 2.5])
    assert pheromones[3] == pytest.approx([2.5, 0.5, 0.5, 0.0])


def test_solve_returns_valid_tour_for_square() -> None:
    cities = [(0, 0), (1, 0), (1, 1), (0, 1)]
    config = Config(ants=10, iterations=50)

    result = solve(cities, config, seed=42)

    assert len(result.best_tour) == len(cities)
    assert set(result.best_tour) == set(range(len(cities)))
    assert len(set(result.best_tour)) == len(cities)
    assert result.best_length >= 4.0
    assert result.best_length <= 2 + 2 * (2**0.5)


def test_solve_is_reproducible_with_same_seed() -> None:
    cities = [(0, 0), (1, 0), (1, 1), (0, 1)]
    config = Config(ants=10, iterations=50)

    first = solve(cities, config, seed=42)
    second = solve(cities, config, seed=42)

    assert first == second


def test_solve_distance_matrix_uses_asymmetric_costs() -> None:
    costs = [
        [0, 1, 10],
        [10, 0, 1],
        [1, 10, 0],
    ]
    config = Config(ants=6, iterations=20)

    result = solve_distance_matrix(costs, config, seed=42)

    assert result.best_length == pytest.approx(
        tour_length(result.best_tour, costs)
    )
    assert result.best_length == pytest.approx(3.0)
    assert result.tour_history[-1] == tuple(result.best_tour)


@pytest.mark.parametrize(
    "costs",
    [
        [[0]],
        [[0, 1], [1]],
        [[1, 1], [1, 0]],
        [[0, 0], [1, 0]],
        [[0, float("inf")], [1, 0]],
        [[0, -1], [1, 0]],
    ],
)
def test_solve_distance_matrix_rejects_invalid_matrices(
    costs: list[list[float]],
) -> None:
    with pytest.raises(ValueError):
        solve_distance_matrix(costs)


def test_history_is_best_so_far() -> None:
    cities = [(0, 0), (1, 0), (1, 1), (0, 1)]
    config = Config(ants=10, iterations=50)

    result = solve(cities, config, seed=42)

    assert len(result.history) == config.iterations
    assert all(
        later <= earlier
        for earlier, later in zip(result.history, result.history[1:])
    )
    assert result.history[-1] == result.best_length
    assert len(result.tour_history) == config.iterations
    assert result.tour_history[-1] == tuple(result.best_tour)
    distances = distance_matrix(cities)
    assert all(
        tour_length(tour, distances) == pytest.approx(length)
        for tour, length in zip(result.tour_history, result.history)
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rho": 0},
        {"rho": 1},
        {"alpha": -1},
        {"beta": -1},
        {"q": 0},
        {"q": -1},
        {"ants": -1},
        {"iterations": 0},
        {"iterations": 1.5},
    ],
)
def test_invalid_configuration_values_raise_value_error(
    kwargs: dict[str, int | float],
) -> None:
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_invalid_city_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        solve([(0, 0)])

    with pytest.raises(ValueError):
        solve([(0, 0), (1, 1), (0, 0)])
