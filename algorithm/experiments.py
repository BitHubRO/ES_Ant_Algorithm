"""Reproducible ACO experiments and CSV result helpers."""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .aco import Config, solve
from .baselines import nearest_neighbor
from .tsp import City

CITY_COUNTS = (10, 30, 50)
SEEDS = (11, 22, 33, 44, 55)
CITY_SEED = 2026

RESULT_FIELDS = (
    "method",
    "city_count",
    "setting",
    "seed",
    "alpha",
    "beta",
    "rho",
    "q",
    "ants",
    "iterations",
    "tour_length",
)
SUMMARY_FIELDS = (
    "method",
    "city_count",
    "setting",
    "alpha",
    "beta",
    "rho",
    "q",
    "ants",
    "iterations",
    "trials",
    "average_length",
    "best_length",
)

ExperimentRow = dict[str, str | int | float | None]
SummaryRow = dict[str, str | int | float]
ParameterSetting = tuple[str, Config]


def int_list(value: str) -> tuple[int, ...]:
    """Parse a comma-separated sequence of integers for command-line options."""
    try:
        return tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from error


def generate_city_sets(
    city_counts: Sequence[int] = CITY_COUNTS,
    seed: int = CITY_SEED,
) -> dict[int, list[City]]:
    """Generate one deterministic set of distinct unit-square coordinates per size."""
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not city_counts:
        raise ValueError("at least one city count is required")
    if any(
        not isinstance(count, int) or isinstance(count, bool) or count < 2
        for count in city_counts
    ):
        raise ValueError("each city count must be an integer of at least 2")
    if len(set(city_counts)) != len(city_counts):
        raise ValueError("city counts must not contain duplicates")

    rng = random.Random(seed)
    city_sets: dict[int, list[City]] = {}
    for count in city_counts:
        points: list[City] = []
        seen: set[City] = set()
        while len(points) < count:
            point = (rng.random(), rng.random())
            if point not in seen:
                points.append(point)
                seen.add(point)
        city_sets[count] = points
    return city_sets


def parameter_settings(
    city_count: int,
    iterations: int = 200,
) -> list[ParameterSetting]:
    """Create baseline and one-parameter-at-a-time ACO configurations."""
    if not isinstance(city_count, int) or isinstance(city_count, bool) or city_count < 2:
        raise ValueError("city_count must be an integer of at least 2")

    baseline = Config(ants=city_count, iterations=iterations)
    settings: list[ParameterSetting] = [("baseline", baseline)]
    for alpha in (0.5, 2.0):
        settings.append(
            (
                f"alpha={alpha:g}",
                Config(alpha=alpha, ants=city_count, iterations=iterations),
            )
        )
    for beta in (2.0, 5.0):
        settings.append(
            (
                f"beta={beta:g}",
                Config(beta=beta, ants=city_count, iterations=iterations),
            )
        )
    for rho in (0.3, 0.5):
        settings.append(
            (
                f"rho={rho:g}",
                Config(rho=rho, ants=city_count, iterations=iterations),
            )
        )
    return settings


def run_experiments(
    city_sets: Mapping[int, Sequence[City]] | None = None,
    seeds: Sequence[int] = SEEDS,
    iterations: int = 200,
    city_seed: int = CITY_SEED,
    progress_callback: Callable[[str], None] | None = None,
) -> list[ExperimentRow]:
    """Run ACO settings and one nearest-neighbor baseline per city set."""
    if not seeds:
        raise ValueError("at least one ACO seed is required")
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seeds):
        raise ValueError("all ACO seeds must be integers")
    if city_sets is None:
        city_sets = generate_city_sets(seed=city_seed)
    if not city_sets:
        raise ValueError("at least one city set is required")

    rows: list[ExperimentRow] = []
    for city_count, cities in city_sets.items():
        if (
            not isinstance(city_count, int)
            or isinstance(city_count, bool)
            or city_count != len(cities)
        ):
            raise ValueError("each city-set key must match its number of cities")

        _, baseline_length = nearest_neighbor(cities)
        if progress_callback is not None:
            progress_callback(f"Finished nearest-neighbor baseline for {city_count} cities")
        rows.append(
            {
                "method": "nearest_neighbor",
                "city_count": city_count,
                "setting": "baseline",
                "seed": None,
                "alpha": None,
                "beta": None,
                "rho": None,
                "q": None,
                "ants": None,
                "iterations": None,
                "tour_length": baseline_length,
            }
        )

        for setting_name, config in parameter_settings(city_count, iterations):
            for seed in seeds:
                result = solve(cities, config, seed=seed)
                rows.append(
                    {
                        "method": "aco",
                        "city_count": city_count,
                        "setting": setting_name,
                        "seed": seed,
                        "alpha": config.alpha,
                        "beta": config.beta,
                        "rho": config.rho,
                        "q": config.q,
                        "ants": config.ants,
                        "iterations": config.iterations,
                        "tour_length": result.best_length,
                    }
                )
                if progress_callback is not None:
                    progress_callback(
                        f"Finished {city_count} cities, {setting_name}, seed {seed}"
                    )
    return rows


def save_results_csv(
    rows: Sequence[ExperimentRow],
    output_path: str | Path,
) -> None:
    """Write raw experiment measurements to a UTF-8 CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize_results(rows: Sequence[ExperimentRow]) -> list[SummaryRow]:
    """Group raw measurements and calculate trial count, average, and best length."""
    grouped: dict[tuple[object, ...], list[float]] = defaultdict(list)
    key_fields = (
        "method",
        "city_count",
        "setting",
        "alpha",
        "beta",
        "rho",
        "q",
        "ants",
        "iterations",
    )

    for row in rows:
        length = row.get("tour_length")
        if not isinstance(length, (int, float)):
            raise ValueError("each result row must have a numeric tour_length")
        key = tuple(row.get(field) for field in key_fields)
        grouped[key].append(float(length))

    summaries: list[SummaryRow] = []
    for key, lengths in grouped.items():
        summary: SummaryRow = {
            field: value
            for field, value in zip(key_fields, key)
            if isinstance(value, (str, int, float))
        }
        summary.update(
            {
                "trials": len(lengths),
                "average_length": sum(lengths) / len(lengths),
                "best_length": min(lengths),
            }
        )
        summaries.append(summary)

    summaries.sort(
        key=lambda row: (
            str(row["method"]),
            int(row["city_count"]),
            str(row["setting"]),
        )
    )
    return summaries


def save_summary_csv(
    rows: Sequence[SummaryRow],
    output_path: str | Path,
) -> None:
    """Write grouped experiment summaries to a UTF-8 CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run reproducible ACO experiments.")
    parser.add_argument(
        "--city-counts",
        type=int_list,
        default=CITY_COUNTS,
        help="comma-separated city counts (default: 10,30,50)",
    )
    parser.add_argument(
        "--seeds",
        type=int_list,
        default=SEEDS,
        help="comma-separated ACO random seeds (default: 11,22,33,44,55)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="ACO iterations per run (default: 200)",
    )
    parser.add_argument(
        "--city-seed",
        type=int,
        default=CITY_SEED,
        help="seed used to generate city coordinates",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="directory for CSV outputs (default: results)",
    )
    args = parser.parse_args()

    city_sets = generate_city_sets(args.city_counts, seed=args.city_seed)
    raw_results = run_experiments(
        city_sets=city_sets,
        seeds=args.seeds,
        iterations=args.iterations,
        progress_callback=print,
    )
    save_results_csv(raw_results, args.output_dir / "aco_experiments.csv")

    summaries = summarize_results(raw_results)
    save_summary_csv(summaries, args.output_dir / "aco_summary.csv")
    print(f"Saved {len(raw_results)} measurements and {len(summaries)} summaries.")
