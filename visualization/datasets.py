"""City data helpers independent of the graphical interface."""

import random

from algorithm.tsp import City


def generate_random_cities(count: int, seed: int) -> list[City]:
    """Return distinct unit-square points in a repeatable, stable index order."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 2:
        raise ValueError("City count must be a whole number of at least 2.")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("Seed must be a whole number.")
    rng = random.Random(seed)
    cities = []
    seen = set()
    while len(cities) < count:
        city = (rng.random(), rng.random())
        if city not in seen:
            cities.append(city)
            seen.add(city)
    return cities
