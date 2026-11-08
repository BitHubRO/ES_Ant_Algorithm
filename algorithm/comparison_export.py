"""CSV comparison exports with reproducible problem and run metadata."""

import csv
import json
from pathlib import Path
from statistics import mean, stdev

from .comparison import METHODS, METHOD_NAMES

FIELDS = ("record_type", "method", "seed", "dataset", "unit", "city_count", "start_city",
          "config_json", "cities_json", "checkpoint", "evaluations", "best_cost", "compute_seconds", "tour_json")


def comparison_rows(reports, metadata, *, include_history=True):
    base = {key: metadata.get(key, "") for key in ("seed", "dataset", "unit", "city_count", "start_city")}
    base["config_json"] = json.dumps(metadata.get("config", {}), ensure_ascii=False, sort_keys=True)
    base["cities_json"] = json.dumps(metadata.get("cities", []), ensure_ascii=False)
    rows = []
    for method in METHODS:
        report = reports[method]
        result = report.result
        def metadata_for(tour):
            values = dict(base)
            if not values["start_city"] and metadata.get("cities"):
                values["start_city"] = metadata["cities"][tour[0]]["name"]
            return values
        rows.append(dict(metadata_for(result.best_tour), record_type="summary", method=METHOD_NAMES[method], checkpoint="",
                         evaluations=report.evaluations, best_cost=result.best_length,
                         compute_seconds=result.compute_seconds, tour_json=json.dumps(list(result.best_tour))))
        if include_history:
            for i, (cost, count, tour) in enumerate(zip(result.history, report.evaluation_history, result.tour_history), 1):
                rows.append(dict(metadata_for(tour), record_type="history", method=METHOD_NAMES[method], checkpoint=i,
                                 evaluations=count, best_cost=cost, compute_seconds="",
                                 tour_json=json.dumps(list(tour))))
    return rows


def write_comparison_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize_trials(trials):
    """Aggregate complete comparisons for one fixed problem and configuration."""
    summaries = []
    for method in METHODS:
        reports = [trial[method] for trial in trials]
        costs = [report.result.best_length for report in reports]
        summaries.append(dict(method=METHOD_NAMES[method], trials=len(costs),
                              average_cost=mean(costs), best_cost=min(costs), worst_cost=max(costs),
                              stddev_cost=stdev(costs) if len(costs) > 1 else 0.0,
                              average_compute_seconds=mean(r.result.compute_seconds for r in reports),
                              tours_per_trial=reports[0].evaluations))
    return summaries
