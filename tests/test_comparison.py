"""Fair budgets, shared costs, reproducibility, timings, exports, and GUI state."""

import csv
import json
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from algorithm.aco import Config, Result, solve
from algorithm.baselines import random_search_distance_matrix
from algorithm.comparison import METHODS, METHOD_NAMES, ComparisonEvent, ComparisonFinished, compare_distance_matrix
from algorithm.comparison_export import comparison_rows, summarize_trials, write_comparison_csv
from algorithm.tsp import distance_matrix, tour_length
from visualization.runner import run_comparison
from visualization.comparison_plot import draw_comparison_plot
from visualization.app import DATASETS
import test_explorer_run as explorer_tests


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.cities = ((0, 0), (1, 0), (1, 1), (0, 1), (0.3, 0.4))
        self.costs = distance_matrix(self.cities)
        self.config = Config(ants=3, iterations=4)

    def test_random_search_is_repeatable_and_respects_partial_final_batch(self):
        events = []
        first = random_search_distance_matrix(self.costs, 11, 7, batch_size=3, progress_callback=events.append)
        second = random_search_distance_matrix(self.costs, 11, 7, batch_size=3)
        self.assertEqual(first, second)
        self.assertEqual(len(events), 4)
        self.assertEqual(len(first.history), 4)
        self.assertTrue(all(a >= b for a, b in zip(first.history, first.history[1:])))
        self.assertAlmostEqual(first.best_length, tour_length(first.best_tour, self.costs))
        for samples, batch in ((0, 1), (True, 1), (5, 0)):
            with self.assertRaises(ValueError):
                random_search_distance_matrix(self.costs, samples, batch_size=batch)

    def test_all_three_share_costs_and_aco_random_have_matched_budgets(self):
        reports = compare_distance_matrix(self.costs, self.config, 7, symmetric_pheromones=True)
        self.assertEqual(set(reports), set(METHODS))
        for method, report in reports.items():
            self.assertEqual(set(report.result.best_tour), set(range(5)))
            self.assertAlmostEqual(report.result.best_length, tour_length(report.result.best_tour, self.costs))
            self.assertGreaterEqual(report.result.compute_seconds, 0)
            self.assertEqual(report.evaluations, 5 if method == "nearest_neighbor" else 12)
        self.assertEqual(reports["aco"].evaluation_history, (3, 6, 9, 12))
        self.assertEqual(reports["random_search"].evaluation_history, (3, 6, 9, 12))
        original = solve(self.cities, self.config, 7)
        self.assertEqual(reports["aco"].result, original)

    def test_asymmetric_costs_are_used_for_every_method(self):
        costs = [[0, 1, 8], [7, 0, 2], [3, 9, 0]]
        reports = compare_distance_matrix(costs, Config(ants=4, iterations=3), 11)
        for report in reports.values():
            self.assertEqual(report.result.best_length, tour_length(report.result.best_tour, costs))

    def test_aco_compute_time_excludes_progress_callback_gaps(self):
        # The 99-second gap models display/wait time between iterations.
        with patch("algorithm.aco.perf_counter", side_effect=(0, 0.1, 1, 1.2, 100, 100.3)):
            result = solve(self.cities, Config(ants=1, iterations=2), 7, progress_callback=lambda event: None)
        self.assertAlmostEqual(result.compute_seconds, 0.6)

    def test_worker_builds_matrix_once_and_emits_complete_protocol(self):
        queue = Queue()
        with patch("visualization.runner.distance_matrix", wraps=distance_matrix) as build:
            run_comparison(self.cities, self.config, 7, queue, live_updates=True, record_pheromones=True)
        build.assert_called_once()
        events = [queue.get_nowait() for _ in range(queue.qsize())]
        self.assertIsInstance(events[-1], ComparisonFinished)
        self.assertEqual(len([event for event in events[:-1] if event.state == "finished"]), 3)
        self.assertEqual(len([event for event in events[:-1] if event.state == "progress"]), 8)
        self.assertEqual(len(events[-1].reports["aco"].result.pheromone_history), 4)

    def test_export_contains_summary_history_and_original_metadata(self):
        reports = compare_distance_matrix(self.costs, self.config, 7)
        metadata = dict(seed=7, dataset="Random cities", unit="coordinate units", city_count=5,
                        config={"ants": 3, "iterations": 4},
                        cities=[dict(name=f"City {i}", coordinates=city) for i, city in enumerate(self.cities)])
        rows = comparison_rows(reports, metadata)
        self.assertEqual(len([row for row in rows if row["record_type"] == "summary"]), 3)
        self.assertEqual(len([row for row in rows if row["record_type"] == "history"]), 9)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "comparison.csv"
            write_comparison_csv(path, rows)
            with path.open(encoding="utf-8-sig", newline="") as source:
                loaded = list(csv.DictReader(source))
        self.assertEqual(json.loads(loaded[0]["config_json"]), metadata["config"])
        self.assertEqual(len(json.loads(loaded[0]["cities_json"])), 5)
        self.assertEqual(loaded[0]["seed"], "7")
        self.assertEqual(loaded[0]["start_city"], f"City {reports['aco'].result.best_tour[0]}")

    def test_repeated_trials_report_average_best_and_variation(self):
        trials = [compare_distance_matrix(self.costs, self.config, seed) for seed in (7, 8, 9)]
        summary = summarize_trials(trials)
        self.assertEqual(len(summary), 3)
        for row in summary:
            self.assertEqual(row["trials"], 3)
            self.assertLessEqual(row["best_cost"], row["average_cost"])
            self.assertLessEqual(row["average_cost"], row["worst_cost"])
        nn = next(row for row in summary if row["method"] == METHOD_NAMES["nearest_neighbor"])
        self.assertEqual(nn["stddev_cost"], 0)

    def test_gui_handles_all_events_and_switches_map_routes(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.running = True
        app.run_ants, app.run_total, app.run_budget = 3, 4, 12
        reports = compare_distance_matrix(self.costs, self.config, 7)
        app.cities = list(self.cities)
        for method, report in reports.items():
            app._handle_comparison_event(ComparisonEvent(method, "running"))
            app._handle_comparison_event(ComparisonEvent(method, "finished", report))
        app.messages.put(ComparisonFinished(reports))
        app._poll_result()
        self.assertFalse(app.running)
        self.assertEqual(set(app.comparison_reports), set(METHODS))
        app.export_button.configure.assert_called_with(state="normal")
        for method in METHODS:
            app.route_method.get.return_value = METHOD_NAMES[method]
            app._route_changed()
            self.assertEqual(set(app._map_tour()), set(range(5)))
            self.assertTrue(app.route_text.insert.called)

    def test_comparison_plot_has_common_axis_and_nn_reference(self):
        canvas = Mock()
        canvas.winfo_width.return_value, canvas.winfo_height.return_value = 600, 300
        reports = compare_distance_matrix(self.costs, self.config, 7)
        draw_comparison_plot(canvas, reports, 12)
        tags = {call.kwargs.get("tags") for call in canvas.create_line.call_args_list}
        self.assertTrue({"aco-curve", "random-curve", "nn-reference"}.issubset(tags))

    def test_gui_rotates_every_completed_method_to_selected_start(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.dataset.get.return_value = DATASETS[1]
        app._dataset_changed()
        app.selected_ids, app.selection_order = {"CJ", "IF", "IS"}, ["IS", "CJ", "IF"]
        app._selection_changed()
        costs = [[0, 1, 2], [1, 0, 1], [2, 1, 0]]
        reports = compare_distance_matrix(costs, Config(iterations=2), 7)
        app.messages.put(ComparisonFinished(reports))
        app._poll_result()
        self.assertTrue(all(report.result.best_tour[0] == 2 for report in app.comparison_reports.values()))

    def test_gui_failure_marks_active_method_failed_and_blocks_export(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.running = True
        app.method_states["random_search"] = "Running"
        app.messages.put(ValueError("invalid costs"))
        app._poll_result()
        self.assertFalse(app.running)
        self.assertEqual(app.method_states["random_search"], "Failed")
        app.export_button.configure.assert_called_with(state="disabled")


if __name__ == "__main__":
    unittest.main()
