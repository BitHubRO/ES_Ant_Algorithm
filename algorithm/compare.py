"""Repeated comparison runs: python -m algorithm.compare --help."""

import argparse
import csv
from dataclasses import asdict
from pathlib import Path

from .aco import Config
from .comparison import compare_distance_matrix
from .comparison_export import comparison_rows, summarize_trials, write_comparison_csv
from .experiments import generate_city_sets, int_list
from .tsp import distance_matrix


def main():
    parser = argparse.ArgumentParser(description="Compare ACO, all-start nearest neighbor, and matched-budget random search.")
    parser.add_argument("--cities", type=int, default=30)
    parser.add_argument("--city-seed", type=int, default=2026)
    parser.add_argument("--seeds", type=int_list, default=(7, 8, 9, 10, 11))
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--ants", type=int, default=0)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=3.0)
    parser.add_argument("--rho", type=float, default=0.4)
    parser.add_argument("--output-dir", type=Path, default=Path("results/comparison"))
    args = parser.parse_args()
    try:
        if not args.seeds:
            raise ValueError("at least one solver seed is required")
        config = Config(alpha=args.alpha, beta=args.beta, rho=args.rho, ants=args.ants, iterations=args.iterations)
        cities = generate_city_sets((args.cities,), args.city_seed)[args.cities]
        costs = distance_matrix(cities)
    except ValueError as error:
        parser.error(str(error))
    metadata = dict(dataset="Random cities", unit="coordinate units", city_count=len(cities),
                    start_city="", config=asdict(config),
                    cities=[dict(name=f"City {i}", coordinates=city) for i, city in enumerate(cities)])
    trials, rows = [], []
    for seed in args.seeds:
        reports = compare_distance_matrix(costs, config, seed, symmetric_pheromones=True)
        trials.append(reports)
        rows.extend(comparison_rows(reports, dict(metadata, seed=seed)))
        print(f"Finished seed {seed}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_comparison_csv(args.output_dir / "trials.csv", rows)
    summaries = summarize_trials(trials)
    with (args.output_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print(f"Saved trial histories and average/best/worst costs to {args.output_dir}")


if __name__ == "__main__":
    main()
