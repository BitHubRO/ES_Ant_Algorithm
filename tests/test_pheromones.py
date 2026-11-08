"""Snapshot correctness, heatmap inspection, and shared history integration."""

import unittest
from unittest.mock import Mock, patch
from queue import Queue

from algorithm.aco import Config, IterationProgress, Result, solve, solve_distance_matrix
from visualization.app import DATASETS
from visualization.pheromone_view import PheromoneView, matrix_cell, pheromone_color
from visualization.runner import run_solver
from visualization.tours import with_start_city
import test_explorer_run as explorer_tests


class PheromoneTests(unittest.TestCase):
    def test_snapshots_capture_evaporation_and_deposits_without_aliasing(self):
        snapshots = []
        with patch("algorithm.aco.build_tour", return_value=[0, 1, 2, 3]):
            result = solve(((0, 0), (1, 0), (1, 1), (0, 1)),
                           Config(ants=1, iterations=2, rho=0.5, q=8), seed=7,
                           record_pheromones=True, progress_callback=snapshots.append)
        first, second = result.pheromone_history
        self.assertEqual(first[0], (0.0, 2.5, 0.5, 2.5))
        self.assertEqual(second[0], (0.0, 3.25, 0.25, 3.25))
        self.assertIs(snapshots[0].pheromones, first)
        self.assertIs(snapshots[1].pheromones, second)
        with self.assertRaises(TypeError):
            first[0][1] = 99
        for matrix in result.pheromone_history:
            self.assertTrue(all(matrix[i][j] == matrix[j][i] for i in range(4) for j in range(4)))

    def test_directed_snapshot_does_not_reinforce_reverse_edges(self):
        costs = [[0, 1, 9, 9], [9, 0, 1, 9], [9, 9, 0, 1], [1, 9, 9, 0]]
        with patch("algorithm.aco.build_tour", return_value=[0, 1, 2, 3]):
            result = solve_distance_matrix(costs, Config(ants=1, iterations=1, rho=0.5, q=8),
                                           record_pheromones=True)
        matrix = result.pheromone_history[0]
        self.assertEqual(matrix[0][1], 2.5)
        self.assertEqual(matrix[1][0], 0.5)

    def test_recording_is_optional_and_does_not_change_the_search(self):
        cities = ((0, 0), (1, 0), (1, 1), (0, 1))
        plain = solve(cities, Config(iterations=5), seed=7)
        recorded = solve(cities, Config(iterations=5), seed=7, record_pheromones=True)
        self.assertEqual(plain.pheromone_history, ())
        self.assertEqual(plain.best_tour, recorded.best_tour)
        self.assertEqual(plain.history, recorded.history)
        self.assertEqual(len(recorded.pheromone_history), 5)
        rotated = with_start_city(recorded, 0)
        self.assertIs(rotated.pheromone_history, recorded.pheromone_history)

    def test_worker_delivers_matching_live_and_final_matrices(self):
        messages = Queue()
        run_solver(((0, 0), (1, 0)), Config(iterations=3), 7, messages,
                   live_updates=True, record_pheromones=True)
        progress = [messages.get_nowait() for _ in range(3)]
        result = messages.get_nowait()
        self.assertEqual([p.pheromones for p in progress], list(result.pheromone_history))

    def test_gui_shares_live_and_replay_matrix_selection(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.running = True
        app.run_total = 2
        first = ((0, 10, 1, 1), (10, 0, 1, 1), (1, 1, 0, 1), (1, 1, 1, 0))
        second = tuple(tuple(value / 2 for value in row) for row in first)
        app._show_progress(IterationProgress(1, 2, (0, 1, 2, 3), 5, first))
        app._show_progress(IterationProgress(2, 2, (0, 1, 2, 3), 4, second))
        self.assertEqual(app.result.pheromone_history, [first, second])
        app.messages.put(Result((0, 1, 2, 3), 4, [5, 4], [(0, 1, 2, 3)] * 2, (first, second)))
        app._poll_result()
        self.assertEqual(app.pheromone_max, 10)
        for i, expected in [(1, first), (2, second)]:
            app.iteration.get.return_value = i
            app._select_iteration()
            args = app.pheromone_view.show.call_args.args
            self.assertIs(args[0], expected)
            self.assertEqual(args[2:], (i, 10))
        app._clear_result()
        app.pheromone_view.show.assert_called_with(None)

    def test_romania_matrix_axes_keep_selected_dataset_order(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.dataset.get.return_value = DATASETS[1]
        app._dataset_changed()
        app.selected_ids = {"CJ", "IF", "IS"}
        app.selection_order = ["IS", "CJ", "IF"]
        app._selection_changed()
        matrix = ((0, 2, 3), (4, 0, 5), (6, 7, 0))
        app.messages.put(Result((0, 1, 2), 4, [4], [(0, 1, 2)], (matrix,)))
        app._poll_result()
        args = app.pheromone_view.show.call_args.args
        self.assertIs(args[0], matrix)
        self.assertEqual(args[1], [("CJ", "Cluj-Napoca"), ("IF", "București"), ("IS", "Iași")])
        self.assertEqual(app.result.best_tour[0], 2)

    def test_color_scale_and_cell_boundaries(self):
        self.assertEqual(pheromone_color(0, 100), "#f1f6fb")
        self.assertEqual(pheromone_color(100, 100), "#173b75")
        self.assertEqual(pheromone_color(0, 0), "#f1f6fb")
        self.assertNotEqual(pheromone_color(1, 100, True), pheromone_color(1, 100, False))
        self.assertEqual(matrix_cell(48, 32, 3, 20), (0, 0))
        self.assertEqual(matrix_cell(68, 72, 3, 20), (2, 1))
        self.assertIsNone(matrix_cell(47, 32, 3, 20))
        self.assertIsNone(matrix_cell(108, 32, 3, 20))

    def test_hover_uses_scrolled_coordinates_and_full_value(self):
        view = PheromoneView.__new__(PheromoneView)
        view.matrix = ((0, 1.2345678901234567), (2, 0))
        view.labels = [("CJ", "Cluj-Napoca"), ("IS", "Iași")]
        view.iteration, view.cell_size = 3, 20
        view.detail, view.canvas = Mock(), Mock()
        view.canvas.canvasx.return_value = 70
        view.canvas.canvasy.return_value = 35
        view._hover(Mock(x=10, y=10))
        text = view.detail.set.call_args.args[0]
        self.assertIn("Cluj-Napoca → Iași", text)
        self.assertIn(repr(view.matrix[0][1]), text)

    def test_large_matrix_draws_only_visible_cells(self):
        view = PheromoneView.__new__(PheromoneView)
        view.matrix = tuple(tuple(0 if i == j else 1 for j in range(100)) for i in range(100))
        view.labels = [(str(i), f"City {i}") for i in range(100)]
        view.maximum, view.canvas, view.legend, view.logarithmic = 1, Mock(), Mock(), Mock()
        view.logarithmic.get.return_value = True
        view.canvas.winfo_ismapped.return_value = True
        view.canvas.winfo_width.return_value = 400
        view.canvas.winfo_height.return_value = 160
        view.canvas.canvasx.side_effect = lambda value: value
        view.canvas.canvasy.side_effect = lambda value: value
        view.redraw()
        self.assertGreater(view.canvas.create_rectangle.call_count, 0)
        self.assertLess(view.canvas.create_rectangle.call_count, 200)

    def test_gui_enables_recording_and_guards_excessive_history(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.record_pheromones.get.return_value = True
        with patch("visualization.app.Thread") as worker:
            app.start_run()
        self.assertTrue(worker.call_args.kwargs["kwargs"]["record_pheromones"])
        app.record_checkbox.configure.assert_called_with(state="disabled")
        app = explorer_tests.ExplorerRunTests().make_app()
        app.record_pheromones.get.return_value = True
        app.cities *= 100
        with patch("visualization.app.Thread") as worker:
            app.start_run()
        worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
