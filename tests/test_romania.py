"""Offline geographic data, city selection, projection, and solver checks."""

from queue import Queue
import unittest
from unittest.mock import Mock, patch

from algorithm.aco import Config, Result
from algorithm.tsp import tour_length
from visualization.app import DATASETS
from visualization.geography import geographic_distance_matrix, load_county_seats, load_county_polygons
from visualization.romania_map import RomaniaMap
from visualization.runner import run_solver
from visualization.tours import with_start_city
import test_explorer_run as explorer_tests


class RomaniaTests(unittest.TestCase):
    def test_county_seats_cover_each_county_once(self):
        seats = load_county_seats()
        expected_codes = set("AB AR AG BC BH BN BT BR BV BZ CS CL CJ CT CV DB DJ GL GR GJ HR HD IL IF IS MM MH MS NT OT PH SM SJ SB SV TR TM TL VS VL VN".split())
        self.assertEqual({seat.id for seat in seats}, expected_codes)
        self.assertEqual(len(seats), 41)
        self.assertEqual(len({seat.coordinates for seat in seats}), 41)
        by_id = {seat.id: seat for seat in seats}
        self.assertEqual(by_id["IF"].name, "București")
        self.assertEqual(by_id["HD"].name, "Deva")
        self.assertEqual(by_id["HR"].name, "Miercurea-Ciuc")
        self.assertTrue(all(20 < seat.lon < 30 and 43 < seat.lat < 49 for seat in seats))
        self.assertTrue(load_county_polygons())

    def test_haversine_known_distance_and_directionality(self):
        # One degree on the equator is about 111.195 km.
        costs = geographic_distance_matrix(((0, 0), (1, 0), (0, 1)))
        self.assertAlmostEqual(costs[0][1], 111.19508, places=4)
        self.assertEqual(costs[0][0], 0)
        self.assertEqual(costs[0][1], costs[1][0])
        # Longitude degrees get shorter toward the poles.
        polar = geographic_distance_matrix(((0, 60), (1, 60)))
        self.assertLess(polar[0][1], 56)

    def test_geographic_validation(self):
        for cities in [(), ((0, 0),), ((1, 1), (1, 1)), ((0, 91), (1, 1)), ((float("nan"), 0), (1, 1))]:
            with self.subTest(cities=cities), self.assertRaises(ValueError):
                geographic_distance_matrix(cities)

    def test_worker_uses_geographic_costs_for_selected_subset(self):
        seats = load_county_seats()[:4]
        cities = tuple(seat.coordinates for seat in seats)
        messages = Queue()
        run_solver(cities, Config(iterations=5), 7, messages, geographic=True)
        result = messages.get_nowait()
        self.assertIsInstance(result, Result)
        self.assertEqual(set(result.best_tour), set(range(4)))
        self.assertAlmostEqual(result.best_length, tour_length(result.best_tour, geographic_distance_matrix(cities)))

    def make_app(self):
        app = explorer_tests.ExplorerRunTests().make_app()
        app.dataset.get.return_value = DATASETS[1]
        app._dataset_changed()
        return app

    def test_marker_click_toggles_selection_and_invalidates_result(self):
        app = self.make_app()
        point = app.romania_map.positions["CJ"]
        click = Mock(x=point[0], y=point[1])
        app._map_clicked(click)
        self.assertEqual(app.selected_ids, {"CJ"})
        self.assertEqual(len(app.cities), 1)
        app.start_button.configure.assert_called_with(state="disabled")
        other = app.romania_map.positions["IS"]
        app._map_clicked(Mock(x=other[0], y=other[1]))
        self.assertEqual(len(app.cities), 2)
        app.start_button.configure.assert_called_with(state="normal")
        app.result = Result([0, 1], 1, [1], [(0, 1)])
        app._map_clicked(click)
        self.assertIsNone(app.result)
        self.assertEqual(app.selected_ids, {"IS"})

    def test_select_all_clear_and_running_guard(self):
        app = self.make_app()
        app._select_all_seats(True)
        self.assertEqual(len(app.cities), 41)
        app.running = True
        app._select_all_seats(False)
        self.assertEqual(len(app.cities), 41)
        app.running = False
        app._select_all_seats(False)
        self.assertEqual(app.cities, [])

    def test_projection_is_stable_when_selection_changes_and_resizes(self):
        view = RomaniaMap()
        canvas = Mock()
        canvas.winfo_width.return_value, canvas.winfo_height.return_value = 800, 500
        view.draw(canvas, set())
        original = dict(view.positions)
        view.draw(canvas, {"CJ", "IS"}, ("CJ", "IS"))
        self.assertEqual(original, view.positions)
        self.assertEqual(view.hit_test(*original["CJ"]), "CJ")
        self.assertIsNone(view.hit_test(-100, -100))
        canvas.winfo_width.return_value = 1000
        view.draw(canvas, {"CJ"})
        self.assertEqual(view.hit_test(*view.positions["CJ"]), "CJ")

    def test_start_uses_selected_order_and_worker_geographic_flag(self):
        app = self.make_app()
        app.selected_ids = {"CJ", "IS", "IF"}
        app._selection_changed()
        self.assertEqual([seat.id for seat in app.selected_seats], ["CJ", "IF", "IS"])
        with patch("visualization.app.Thread") as worker:
            app.start_run()
        self.assertTrue(worker.call_args.kwargs["kwargs"]["geographic"])
        self.assertEqual(worker.call_args.kwargs["args"][0], tuple(app.cities))

    def test_completed_route_uses_names_and_kilometers(self):
        app = self.make_app()
        app.selected_ids = {"CJ", "IS", "IF"}
        app._selection_changed()
        app.messages.put(Result([0, 2, 1], 100, [100], [(0, 2, 1)]))
        app._poll_result()
        self.assertIn("km", app.best_distance.set.call_args.args[0])
        app.route_text.insert.assert_called_with("1.0", "Cluj-Napoca → Iași → București → Cluj-Napoca")

    def click_seat(self, app, city_id):
        x, y = app.romania_map.positions[city_id]
        app._map_clicked(Mock(x=x, y=y))

    def test_first_clicked_city_is_start_before_and_after_run(self):
        app = self.make_app()
        for city_id in ("IS", "CJ", "IF"):
            self.click_seat(app, city_id)
        self.assertEqual(app.selection_order, ["IS", "CJ", "IF"])
        # Input indices remain stable; Iași's index is 2, not 0.
        self.assertEqual([seat.id for seat in app.selected_seats], ["CJ", "IF", "IS"])
        app.start_label.set.assert_called_with("Start: Iași")
        markers = app.map_canvas.create_oval.call_args_list[-41:]
        start_marker = markers[[seat.id for seat in app.romania_map.seats].index("IS")]
        self.assertEqual(start_marker.kwargs["fill"], "#d66a24")
        app.messages.put(Result([0, 2, 1], 100, [120, 100], [(1, 0, 2), (0, 2, 1)]))
        app._poll_result()
        self.assertEqual(app.result.best_tour[0], 2)
        self.assertTrue(all(tour[0] == 2 for tour in app.result.tour_history))
        for frame in (1, 2):
            app.iteration.get.return_value = frame
            app._select_iteration()
            route = app.route_text.insert.call_args.args[1]
            self.assertTrue(route.startswith("Iași → "))
            self.assertTrue(route.endswith(" → Iași"))

    def test_removal_reselection_and_bulk_selection_preserve_click_order(self):
        app = self.make_app()
        for city_id in ("IS", "CJ", "IF"):
            self.click_seat(app, city_id)
        self.click_seat(app, "IS")
        self.assertEqual(app.selection_order, ["CJ", "IF"])
        app.start_label.set.assert_called_with("Start: Cluj-Napoca")
        self.click_seat(app, "IS")
        self.assertEqual(app.selection_order, ["CJ", "IF", "IS"])
        app._select_all_seats(True)
        self.assertEqual(app.selection_order[0], "CJ")
        self.assertEqual(len(set(app.selection_order)), 41)
        app._select_all_seats(False)
        self.assertEqual(app.selection_order, [])
        app.start_label.set.assert_called_with("Start: --")
        app._select_all_seats(True)
        self.assertEqual(app.selection_order[0], "AB")

    def test_rotation_preserves_directed_edges_cost_and_original_result(self):
        costs = [[0, 2, 9], [7, 0, 3], [4, 8, 0]]
        tours = [(1, 2, 0), (2, 0, 1)]
        lengths = [tour_length(tour, costs) for tour in tours]
        original = Result([2, 0, 1], lengths[-1], lengths, tours)
        rotated = with_start_city(original, 0)
        for before, after in zip(original.tour_history, rotated.tour_history):
            edges = lambda tour: {(city, tour[(i + 1) % len(tour)]) for i, city in enumerate(tour)}
            self.assertEqual(edges(before), edges(after))
            self.assertEqual(after[0], 0)
            self.assertEqual(tour_length(before, costs), tour_length(after, costs))
        self.assertEqual(rotated.best_tour, (0, 1, 2))
        self.assertIs(rotated.history, original.history)
        self.assertEqual(rotated.best_length, original.best_length)
        self.assertEqual(original.best_tour, [2, 0, 1])

    def test_dataset_change_and_reset_clear_start(self):
        for reset in (False, True):
            with self.subTest(reset=reset):
                app = self.make_app()
                self.click_seat(app, "IS")
                if reset:
                    app.reset_form()
                else:
                    app.dataset.get.return_value = DATASETS[0]
                    app._dataset_changed()
                self.assertEqual(app.selection_order, [])
                self.assertEqual(app.selected_ids, set())
                app.start_label.set.assert_called_with("Start: --")


if __name__ == "__main__":
    unittest.main()
