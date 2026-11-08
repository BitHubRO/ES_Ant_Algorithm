"""Checks runnable with unittest, without third-party packages or a window."""

import random
import unittest

from algorithm.tsp import distance_matrix
from visualization.datasets import generate_random_cities


class RandomCityTests(unittest.TestCase):
    def test_repeatability_and_different_seeds(self):
        first = generate_random_cities(30, 7)
        self.assertEqual(first, generate_random_cities(30, 7))
        self.assertNotEqual(first, generate_random_cities(30, 8))

    def test_points_are_distinct_bounded_and_usable_by_solver(self):
        cities = generate_random_cities(50, 7)
        self.assertEqual(len(cities), 50)
        self.assertEqual(len(set(cities)), 50)
        self.assertTrue(all(0 <= coordinate < 1 for city in cities for coordinate in city))
        self.assertEqual(len(distance_matrix(cities)), 50)

    def test_generation_does_not_change_global_random_state(self):
        before = random.getstate()
        generate_random_cities(20, 7)
        self.assertEqual(before, random.getstate())

    def test_invalid_inputs_are_rejected(self):
        for count, seed in [(0, 7), (1, 7), (2.5, 7), (True, 7), (2, 1.5), (2, True)]:
            with self.subTest(count=count, seed=seed), self.assertRaises(ValueError):
                generate_random_cities(count, seed)


if __name__ == "__main__":
    unittest.main()
