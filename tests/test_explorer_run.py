"""Solver integration and GUI state tests without opening a desktop window."""

from queue import Queue
from threading import Thread
import unittest
from unittest.mock import Mock, patch

from algorithm.aco import Config, Result
from algorithm.tsp import distance_matrix, tour_length
from visualization.app import DATASETS, DEFAULTS, ExplorerApp
from visualization.runner import run_solver


class ExplorerRunTests(unittest.TestCase):
    def make_app(self):
        app = ExplorerApp.__new__(ExplorerApp)
        app.root = Mock()
        app.running = False
        app.playing = False
        app.animation_after = None
        app.animate_iterations = Mock()
        app.animate_iterations.get.return_value = False
        app.playback_speed = Mock()
        app.playback_speed.get.return_value = "Normal (300 ms)"
        app.result = None
        app.cities = [(0, 0), (1, 0), (1, 1), (0, 1)]
        app.romania_map = None
        app.selected_ids = set()
        app.selection_order = []
        app.selected_seats = []
        app.loaded_seed = 7
        app.messages = Queue()
        app.dataset = Mock()
        app.dataset.get.return_value = DATASETS[0]
        app.fields = {name: Mock() for name in DEFAULTS}
        for name, value in DEFAULTS.items():
            app.fields[name].get.return_value = value
        app.input_widgets = []
        for name in ("feedback", "status", "best_distance", "slider", "iteration",
                     "iteration_label", "selector", "city_count_entry", "generate_button",
                     "start_button", "reset_button", "check_button", "map_canvas", "chart",
                     "play_button", "speed_selector", "selection_toolbar", "attribution",
                     "selection_label", "map_hint", "select_all_button", "clear_selection_button",
                     "route_text", "start_label"):
            setattr(app, name, Mock())
        app.iteration.get.return_value = 1
        app.map_canvas.winfo_width.return_value = 600
        app.map_canvas.winfo_height.return_value = 400
        app.chart.winfo_width.return_value = 600
        app.chart.winfo_height.return_value = 150
        return app

    def test_background_result_scores_loaded_cities(self):
        cities = ((0, 0), (1, 0), (1, 1), (0, 1))
        messages = Queue()
        worker = Thread(target=run_solver, args=(cities, Config(iterations=5), 7, messages))
        worker.start()
        message = messages.get(timeout=5)
        worker.join(timeout=5)
        self.assertIsInstance(message, Result)
        self.assertAlmostEqual(message.best_length, tour_length(message.best_tour, distance_matrix(cities)))
        self.assertEqual(len(message.history), 5)

    def test_worker_delivers_errors(self):
        messages = Queue()
        with patch("visualization.runner.solve", side_effect=ValueError("invalid costs")):
            run_solver(((0, 0), (1, 0)), Config(), 7, messages)
        self.assertIsInstance(messages.get_nowait(), ValueError)

    def test_start_snapshots_loaded_cities_and_prevents_duplicate_runs(self):
        app = self.make_app()
        # A pending count edit must not change the loaded problem.
        app.fields["city_count"].get.return_value = "not applied yet"
        with patch("visualization.app.Thread") as worker:
            app.start_run()
            app.start_run()
        self.assertTrue(app.running)
        worker.assert_called_once()
        args = worker.call_args.kwargs["args"]
        self.assertEqual(args[0], tuple(app.cities))
        self.assertEqual(args[2], 7)
        app.start_button.configure.assert_called_with(state="disabled")
        app.root.after.assert_called_once()

    def test_invalid_settings_do_not_launch_worker(self):
        app = self.make_app()
        app.fields["rho"].get.return_value = "1"
        with patch("visualization.app.Thread") as worker:
            app.start_run()
        worker.assert_not_called()
        self.assertFalse(app.running)

    def test_poll_handles_success_and_draws_closed_route(self):
        app = self.make_app()
        result = Result([0, 1, 2, 3], 4.0, [4.0], [(0, 1, 2, 3)])
        app.running = True
        app.messages.put(result)
        app._poll_result()
        self.assertFalse(app.running)
        self.assertIs(app.result, result)
        edges = app.map_canvas.create_line.call_args_list
        self.assertEqual(len(edges), 4)
        # The final edge ends where the first edge starts.
        self.assertEqual(edges[-1].args[2:4], edges[0].args[:2])
        app.start_button.configure.assert_called_with(state="normal")

    def test_poll_failure_restores_controls(self):
        app = self.make_app()
        app.running = True
        app.messages.put(ValueError("numerical error"))
        app._poll_result()
        self.assertFalse(app.running)
        self.assertIsNone(app.result)
        app.feedback.set.assert_called_with("numerical error")
        app.reset_button.configure.assert_called_with(state="normal")

    def test_empty_queue_reschedules_and_history_selection_is_bounded(self):
        app = self.make_app()
        app._poll_result()
        app.root.after.assert_called_once_with(100, app._poll_result)
        app.result = Result([0, 1, 2, 3], 4, [5, 4], [(0, 2, 1, 3), (0, 1, 2, 3)])
        app.iteration.get.return_value = 999
        self.assertEqual(app._iteration_index(), 1)
        app.iteration.get.return_value = -5
        self.assertEqual(app._iteration_index(), 0)

    def test_dataset_change_clears_results(self):
        app = self.make_app()
        app.result = Result([0, 1, 2, 3], 4, [4], [(0, 1, 2, 3)])
        app.dataset.get.return_value = DATASETS[1]
        app._dataset_changed()
        self.assertIsNone(app.result)
        self.assertEqual(app.cities, [])
        app.slider.configure.assert_called_with(state="disabled", to=1)

    def playback_app(self):
        app = self.make_app()
        app.animate_iterations.get.return_value = True
        app.result = Result([0, 1, 2, 3], 4, [5, 4.5, 4],
                            [(0, 2, 1, 3), (0, 1, 2, 3), (0, 1, 2, 3)])
        # Model a real Tk variable so timer steps can update its value.
        position = [3]
        app.iteration.get.side_effect = lambda: position[0]
        app.iteration.set.side_effect = lambda value: position.__setitem__(0, value)
        return app

    def test_replay_visits_each_iteration_then_stops(self):
        app = self.playback_app()
        app.toggle_playback()
        self.assertEqual(app.iteration.get(), 1)
        self.assertTrue(app.playing)
        app.root.after.assert_called_with(300, app._advance_frame)
        app._advance_frame()
        self.assertEqual(app.iteration.get(), 2)
        app._advance_frame()
        self.assertEqual(app.iteration.get(), 3)
        self.assertFalse(app.playing)

    def test_pause_cancels_timer_and_resume_keeps_position(self):
        app = self.playback_app()
        app.root.after.return_value = "frame-1"
        app.toggle_playback()
        app._advance_frame()
        app.toggle_playback()
        app.root.after_cancel.assert_called_with("frame-1")
        self.assertFalse(app.playing)
        app.toggle_playback()
        self.assertEqual(app.iteration.get(), 2)

    def test_disabling_animation_and_clearing_result_cancel_playback(self):
        app = self.playback_app()
        app.toggle_playback()
        app.animate_iterations.get.return_value = False
        app._animation_option_changed()
        self.assertFalse(app.playing)
        app.play_button.configure.assert_called_with(state="disabled", text="Play")
        app.animate_iterations.get.return_value = True
        app.toggle_playback()
        app._clear_result()
        self.assertFalse(app.playing)
        self.assertIsNone(app.result)
        self.assertIsNone(app.animation_after)

    def test_manual_slider_pauses_and_speed_changes_next_delay(self):
        app = self.playback_app()
        app.toggle_playback()
        app.playback_speed.get.return_value = "Fast (100 ms)"
        app._advance_frame()
        app.root.after.assert_called_with(100, app._advance_frame)
        app._select_iteration("2")
        self.assertFalse(app.playing)

    def test_unchecked_option_does_not_start_playback(self):
        app = self.playback_app()
        app.animate_iterations.get.return_value = False
        app.toggle_playback()
        app.root.after.assert_not_called()
        self.assertEqual(app.iteration.get(), 3)

    def test_completion_autoplays_only_when_selected(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                app = self.playback_app()
                result = app.result
                app.result = None
                app.animate_iterations.get.return_value = enabled
                app.messages.put(result)
                app._poll_result()
                self.assertEqual(app.playing, enabled)
                self.assertEqual(app.iteration.get(), 1 if enabled else 3)


if __name__ == "__main__":
    unittest.main()
