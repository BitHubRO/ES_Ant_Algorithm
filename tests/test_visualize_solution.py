import pytest

from algorithm.visualize_solution import (
    make_demo_road_cost_matrix,
    scale_city_positions,
    scale_history,
)


def test_scale_city_positions_preserves_order_and_canvas_bounds() -> None:
    cities = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]

    positions = scale_city_positions(cities, width=800, height=600, padding=40)

    assert len(positions) == len(cities)
    assert all(40 <= x <= 760 and 40 <= y <= 560 for x, y in positions)
    assert positions[0][1] == positions[1][1]
    assert positions[2][1] == positions[3][1]
    assert positions[0][0] == positions[3][0]
    assert positions[1][0] == positions[2][0]


def test_scale_city_positions_handles_zero_width_or_height() -> None:
    vertical = scale_city_positions([(2.0, 0.0), (2.0, 5.0)], 400, 300)
    horizontal = scale_city_positions([(0.0, 3.0), (5.0, 3.0)], 400, 300)

    assert vertical[0][0] == vertical[1][0]
    assert horizontal[0][1] == horizontal[1][1]


def test_scale_city_positions_rejects_invalid_dimensions_or_empty_input() -> None:
    with pytest.raises(ValueError):
        scale_city_positions([], 800, 600)
    with pytest.raises(ValueError):
        scale_city_positions([(0.0, 0.0)], 80, 600, padding=40)


def test_scale_history_maps_first_and_best_values_to_chart_bounds() -> None:
    points = scale_history([10.0, 8.0, 5.0], width=400, height=300, padding=30)

    assert points[0] == pytest.approx((30, 30))
    assert points[-1] == pytest.approx((370, 270))
    assert points[1][0] == pytest.approx(200)
    assert 30 <= points[1][1] <= 270


def test_scale_history_centers_single_or_constant_history() -> None:
    single = scale_history([7.0], width=400, height=300)
    constant = scale_history([7.0, 7.0, 7.0], width=400, height=300)

    assert single == [(200, 150)]
    assert [point[1] for point in constant] == [150, 150, 150]


def test_scale_history_rejects_empty_nonfinite_or_too_small_chart() -> None:
    with pytest.raises(ValueError):
        scale_history([], 400, 300)
    with pytest.raises(ValueError):
        scale_history([1.0, float("inf")], 400, 300)
    with pytest.raises(ValueError):
        scale_history([1.0], 80, 300, padding=40)


def test_solver_history_stores_best_tour_at_each_iteration() -> None:
    from algorithm.aco import Config, solve
    from algorithm.tsp import distance_matrix, tour_length

    cities = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    result = solve(cities, Config(ants=4, iterations=8), seed=17)
    distances = distance_matrix(cities)

    assert len(result.history) == len(result.tour_history) == 8
    assert all(
        tour_length(tour, distances) == pytest.approx(length)
        for tour, length in zip(result.tour_history, result.history)
    )
    assert result.tour_history[-1] == tuple(result.best_tour)


def test_show_tour_requires_matching_nonempty_histories() -> None:
    from algorithm.visualize_solution import show_tour

    with pytest.raises(ValueError):
        show_tour([(0.0, 0.0), (1.0, 0.0)], [1.0], [])
    with pytest.raises(ValueError):
        show_tour([(0.0, 0.0), (1.0, 0.0)], [], [])


def test_demo_road_cost_matrix_is_positive_directed_and_not_euclidean() -> None:
    cities = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

    costs = make_demo_road_cost_matrix(cities)

    assert len(costs) == len(cities)
    assert all(costs[i][i] == 0 for i in range(len(cities)))
    assert all(
        costs[i][j] > 0
        for i in range(len(cities))
        for j in range(len(cities))
        if i != j
    )
    assert any(
        costs[i][j] != pytest.approx(costs[j][i])
        for i in range(len(cities))
        for j in range(i + 1, len(cities))
    )


def test_matrix_demo_aco_history_matches_displayed_matrix_costs() -> None:
    from algorithm.aco import Config, solve_distance_matrix
    from algorithm.tsp import tour_length

    cities = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    costs = make_demo_road_cost_matrix(cities)
    result = solve_distance_matrix(
        costs,
        Config(ants=4, iterations=6),
        seed=23,
    )

    assert len(result.history) == len(result.tour_history) == 6
    assert all(
        tour_length(tour, costs) == pytest.approx(length)
        for tour, length in zip(result.tour_history, result.history)
    )
