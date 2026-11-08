"""Verify live solver events, paced computation, and incremental GUI updates."""

from queue import Queue
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from algorithm.aco import Config, IterationProgress, Result, solve, solve_distance_matrix
from algorithm.tsp import distance_matrix, tour_length
from visualization.app import DATASETS
from visualization.runner import run_solver
import test_explorer_run as explorer_tests


class LiveProgressTests(unittest.TestCase):
    def test_callback_reports_each_iteration_without_changing_result(self):
        cities = ((0, 0), (1, 0), (1, 1), (0, 1), (0.2, 0.4))
        for geographic in (False, True):
            with self.subTest(matrix_mode=geographic):
                solver = solve_distance_matrix if geographic else solve
                problem = distance_matrix(cities) if geographic else cities
                snapshots = []
                expected = solver(problem, Config(iterations=10), seed=7)
                actual = solver(problem, Config(iterations=10), seed=7, progress_callback=snapshots.append)
                self.assertEqual(actual, expected)
                self.assertEqual([p.iteration for p in snapshots], list(range(1, 11)))
                self.assertTrue(all(p.total_iterations == 10 for p in snapshots))
                self.assertEqual([p.best_length for p in snapshots], actual.history)
                self.assertEqual([p.best_tour for p in snapshots], actual.tour_history)
                for p in snapshots:
                    self.assertAlmostEqual(p.best_length, tour_length(p.best_tour, distance_matrix(cities)))

    def test_live_worker_emits_events_before_final_result_and_delays_between_iterations(self):
        messages = Queue()
        cancellation = Mock()
        cancellation.is_set.return_value = False
        cancellation.wait.return_value = False
        run_solver(((0, 0), (1, 0), (0, 1)), Config(iterations=3), 7, messages,
                   live_updates=True, iteration_delay=0.3, cancel_event=cancellation)
        events = [messages.get_nowait() for _ in range(messages.qsize())]
        self.assertEqual([p.iteration for p in events[:-1]], [1, 2, 3])
        self.assertIsInstance(events[-1], Result)
        self.assertEqual(cancellation.wait.call_count, 2)
        cancellation.wait.assert_called_with(0.3)

    def test_fast_mode_keeps_single_final_message(self):
        messages = Queue()
        run_solver(((0, 0), (1, 0), (0, 1)), Config(iterations=3), 7, messages)
        self.assertEqual(messages.qsize(), 1)
        self.assertIsInstance(messages.get_nowait(), Result)

    def test_background_can_be_interrupted_during_delay(self):
        messages, cancel = Queue(), Event()
        worker = Thread(target=run_solver, args=(((0, 0), (1, 0)), Config(iterations=3), 7, messages),
                        kwargs=dict(live_updates=True, iteration_delay=10, cancel_event=cancel), daemon=True)
        worker.start()
        self.assertIsInstance(messages.get(timeout=3), IterationProgress)
        self.assertTrue(worker.is_alive())
        cancel.set()
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(messages.get(timeout=3), InterruptedError)

    def test_gui_renders_partial_history_while_controls_stay_locked(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.running = True
        app.run_total = 10
        app.messages.put(IterationProgress(1, 10, (0, 1, 2, 3), 5))
        app._poll_result()
        self.assertTrue(app.running)
        self.assertEqual(app.result.history, [5])
        app.messages.put(IterationProgress(2, 10, (0, 1, 2, 3), 4))
        app._poll_result()
        self.assertEqual(app.result.history, [5, 4])
        # The x axis covers all 10 iterations, not just the two completed ones.
        curve = next(call for call in app.chart.create_line.call_args_list if call.kwargs.get("width") == 2)
        self.assertAlmostEqual(curve.args[0], 45)
        self.assertAlmostEqual(curve.args[2], 45 + (600 - 90) / 9)
        self.assertIn("/10", app.iteration_label.set.call_args.args[0])

    def test_gui_uses_requested_delay_and_freezes_live_options(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.slow_live.get.return_value = True
        app.live_speed.get.return_value = "Slow (700 ms)"
        with patch("visualization.app.Thread") as worker:
            app.start_run()
        options = worker.call_args.kwargs["kwargs"]
        self.assertTrue(options["live_updates"])
        self.assertEqual(options["iteration_delay"], 0.7)
        app.live_checkbox.configure.assert_called_with(state="disabled")
        app.live_speed_selector.configure.assert_called_with(state="disabled")

    def test_live_romania_tours_keep_first_selected_start(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.dataset.get.return_value = DATASETS[1]
        app._dataset_changed()
        app.selected_ids = {"CJ", "IF", "IS"}
        app.selection_order = ["IS", "CJ", "IF"]
        app._selection_changed()
        app.running = True
        app.run_total = 3
        app._show_progress(IterationProgress(1, 3, (0, 1, 2), 100))
        self.assertEqual(app.result.best_tour[0], 2)
        route = app.route_text.insert.call_args.args[1]
        self.assertTrue(route.startswith("Iași → "))
        self.assertTrue(route.endswith(" → Iași"))

    def test_short_chart_keeps_cost_curve_instead_of_placeholder(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.result = Result((0, 1, 2, 3), 4, [6, 5, 4], [(0, 1, 2, 3)] * 3)
        app.chart.winfo_height.return_value = 60
        app._draw_chart()
        curves = [call for call in app.chart.create_line.call_args_list
                  if call.kwargs.get("tags") == "cost-curve"]
        self.assertEqual(len(curves), 1)
        self.assertTrue(all(0 <= y <= 60 for y in curves[0].args[1::2]))


if __name__ == "__main__":
    unittest.main()
