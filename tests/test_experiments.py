import csv

import pytest

from algorithm.experiments import (
    generate_city_sets,
    parameter_settings,
    run_experiments,
    save_results_csv,
    save_summary_csv,
    summarize_results,
)


def test_generate_city_sets_is_reproducible_and_has_distinct_points() -> None:
    first = generate_city_sets((4, 7), seed=19)
    second = generate_city_sets((4, 7), seed=19)

    assert first == second
    assert set(first) == {4, 7}
    assert all(len(set(cities)) == count for count, cities in first.items())
    assert all(
        0.0 <= coordinate <= 1.0
        for cities in first.values()
        for city in cities
        for coordinate in city
    )


@pytest.mark.parametrize(
    "counts",
    [(), (1,), (3, 3), (2, 0)],
)
def test_generate_city_sets_rejects_invalid_counts(
    counts: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError):
        generate_city_sets(counts)


def test_parameter_settings_change_only_one_parameter_at_a_time() -> None:
    settings = parameter_settings(city_count=6, iterations=3)
    baseline_name, baseline = settings[0]

    assert baseline_name == "baseline"
    assert len(settings) == 7
    assert baseline.ants == 6
    assert baseline.iterations == 3

    for name, config in settings[1:]:
        changed = [
            attribute
            for attribute in ("alpha", "beta", "rho")
            if getattr(config, attribute) != getattr(baseline, attribute)
        ]
        assert len(changed) == 1
        assert name.startswith(f"{changed[0]}=")
        assert config.q == baseline.q
        assert config.ants == baseline.ants
        assert config.iterations == baseline.iterations


def test_run_experiments_reuses_city_set_and_runs_baseline_once() -> None:
    city_sets = {4: [(0, 0), (1, 0), (1, 1), (0, 1)]}
    rows = run_experiments(city_sets, seeds=(3, 8), iterations=2)

    baseline_rows = [row for row in rows if row["method"] == "nearest_neighbor"]
    aco_rows = [row for row in rows if row["method"] == "aco"]

    assert len(baseline_rows) == 1
    assert baseline_rows[0]["tour_length"] == pytest.approx(4.0)
    assert len(aco_rows) == 7 * 2
    assert {row["seed"] for row in aco_rows} == {3, 8}
    assert all(row["city_count"] == 4 for row in rows)


def test_run_experiments_rejects_empty_seeds() -> None:
    with pytest.raises(ValueError):
        run_experiments({2: [(0, 0), (1, 0)]}, seeds=(), iterations=1)


def test_summarize_results_calculates_average_and_best() -> None:
    rows = [
        {
            "method": "aco",
            "city_count": 3,
            "setting": "baseline",
            "seed": 1,
            "alpha": 1.0,
            "beta": 3.0,
            "rho": 0.4,
            "q": 100.0,
            "ants": 3,
            "iterations": 10,
            "tour_length": 8.0,
        },
        {
            "method": "aco",
            "city_count": 3,
            "setting": "baseline",
            "seed": 2,
            "alpha": 1.0,
            "beta": 3.0,
            "rho": 0.4,
            "q": 100.0,
            "ants": 3,
            "iterations": 10,
            "tour_length": 6.0,
        },
    ]

    summary = summarize_results(rows)

    assert len(summary) == 1
    assert summary[0]["trials"] == 2
    assert summary[0]["average_length"] == pytest.approx(7.0)
    assert summary[0]["best_length"] == 6.0


def test_csv_writers_write_headers_and_rows(tmp_path) -> None:
    raw_rows = run_experiments(
        {3: [(0, 0), (1, 0), (0, 1)]},
        seeds=(5,),
        iterations=1,
    )
    raw_path = tmp_path / "nested" / "raw.csv"
    summary_path = tmp_path / "nested" / "summary.csv"

    save_results_csv(raw_rows, raw_path)
    save_summary_csv(summarize_results(raw_rows), summary_path)

    with raw_path.open(newline="", encoding="utf-8") as csv_file:
        raw_csv = list(csv.DictReader(csv_file))
    with summary_path.open(newline="", encoding="utf-8") as csv_file:
        summary_csv = list(csv.DictReader(csv_file))

    assert len(raw_csv) == len(raw_rows)
    assert len(summary_csv) == 8
    assert raw_csv[0]["method"] == "nearest_neighbor"
    assert summary_csv[0]["trials"] == "1"
