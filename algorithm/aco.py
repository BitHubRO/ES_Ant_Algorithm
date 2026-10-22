# ACO SOLVER WORKSHEET
#
# This file is intentionally pseudocode, not a working Python implementation.
# Work through the steps in order and replace each section with Python.
#
# Shared concepts:
#   cities      - sequence of (x, y) coordinates
#   distances   - matrix from tsp.distance_matrix(cities)
#   tour        - city indices in visit order; do not repeat the start at end
#   pheromones  - matrix where pheromones[i][j] is the strength of edge i -> j
#
# Suggested imports when you begin writing real code:
#   dataclass
#   random
#   City, distance_matrix, tour_length from tsp.py
#
# STEP 1 — Define the run settings
# ---------------------------------
# Create a configuration type with:
#   alpha       = 1.0       # pheromone influence
#   beta        = 3.0       # preference for shorter edges
#   rho         = 0.4       # evaporation rate; must be greater than 0, less than 1
#   q           = 100.0     # pheromone deposited, must be positive
#   ants        = 0         # 0 means use one ant per city
#   iterations  = 200       # number of algorithm rounds; must be at least 1
#

from collections.abc import Sequence
import dataclasses
import math
import random
from .tsp import (
    City,
    distance_matrix,
    tour_length,
    validate_distance_matrix,
)


@dataclasses.dataclass
class Config:
    alpha: float = 1.0       # pheromone influence
    beta: float = 3.0        # preference for shorter edges
    rho: float = 0.4         # evaporation rate; must be greater than 0, less than 1
    q: float = 100.0         # pheromone deposited, must be positive
    ants: int = 0            # 0 means use one ant per city
    iterations: int = 200    # number of algorithm rounds; must be at least 1

    def __post_init__(self):
        for name, value in (("alpha", self.alpha), ("beta", self.beta), ("rho", self.rho), ("q", self.q)):
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if self.alpha < 0 or self.beta < 0:
            raise ValueError("alpha and beta must be non-negative")
        if not 0 < self.rho < 1:
            raise ValueError("rho must be between 0 and 1")
        if self.q <= 0:
            raise ValueError("q must be positive")
        if not isinstance(self.ants, int) or isinstance(self.ants, bool) or self.ants < 0:
            raise ValueError("ants must be a non-negative integer")
        if (
            not isinstance(self.iterations, int)
            or isinstance(self.iterations, bool)
            or self.iterations < 1
        ):
            raise ValueError("iterations must be a positive integer")


# When a configuration is created, validate its values.
# If any value is invalid, raise ValueError with a helpful message.
#
# Create a result type containing:
#   best_tour   - tuple/list of city indices for the best closed tour
#   best_length - length of that tour, including the last-to-first edge
#   history     - best_length after each iteration
#
#

@dataclasses.dataclass
class Result:
    best_tour: Sequence[int]
    best_length: float
    history: Sequence[float]
    tour_history: Sequence[tuple[int, ...]]

# STEP 2 — Choose the next city
# -----------------------------
# Inputs:
#   current     - the ant's current city index
#   unvisited   - candidate city indices not visited by this ant yet
#   pheromones  - current pheromone matrix
#   distances   - distance matrix from tsp.distance_matrix
#   config      - run settings
#   rng         - seeded random-number generator shared by this solver run
#
# For each city j in unvisited:
#   heuristic(j) = 1 / distances[current][j]
#   weight(j) = pheromones[current][j] ** alpha * heuristic(j) ** beta
#
# Convert weights to a probability distribution:
#   total_weight = sum of all candidate weights
#   probability(j) = weight(j) / total_weight
#
# Roulette-wheel selection:
#   draw random_number from [0, total_weight)
#   running_total = 0
#   for each candidate and its weight:
#       add weight to running_total
#       if random_number < running_total:
#           return that candidate
#
# Pseudocode function:
#   choose_next_city(current, unvisited, pheromones, distances, config, rng):
#       calculate each candidate's weight
#       choose one candidate by roulette-wheel selection
#       return its city index
#
# Note: coordinates must be distinct, so distances between different cities
# should be positive. If you support any other graph type later, handle
# zero-distance or unavailable edges explicitly.
#

def choose_next_city(current, unvisited, pheromones, distances, config, rng):
    weights = []
    for j in unvisited:
        heuristic = 1 / distances[current][j]
        weight = (pheromones[current][j] ** config.alpha) * (heuristic ** config.beta)
        weights.append(weight)

    total_weight = sum(weights)
    random_number = rng.uniform(0, total_weight)
    running_total = 0
    for j, weight in enumerate(weights):
        running_total += weight
        if random_number < running_total:
            return unvisited[j]

    # If we reach here, it means all weights are zero (or very small)
    # In that case, we can return a random unvisited city
    return rng.choice(unvisited)


#
# STEP 3 — Build one ant's tour
# -----------------------------
# Inputs:
#   city_count, pheromones, distances, config, rng
#
# Pseudocode function:
#   build_tour(...):
#       start = choose a random city index from 0 to city_count - 1
#       tour = [start]
#       unvisited = every city index except start
#
#       while unvisited is not empty:
#           current = last city in tour
#           next_city = choose_next_city(current, unvisited, ...)
#           append next_city to tour
#           remove next_city from unvisited
#
#       return tour
#
# The tour must contain each city exactly once. Do not append start to the end;
# tsp.tour_length closes the loop when it measures the tour.
#

def build_tour(city_count, pheromones, distances, config, rng):
    start = rng.randint(0, city_count - 1)
    tour = [start]
    unvisited = set(range(city_count)) - {start}

    while unvisited:
        current = tour[-1]
        next_city = choose_next_city(current, list(unvisited), pheromones, distances, config, rng)
        tour.append(next_city)
        unvisited.remove(next_city)

    return tour

#
# STEP 4 — Update pheromones
# --------------------------
# Inputs:
#   pheromones, tours_with_lengths, config
#
# First evaporate pheromone on every edge:
#   for every pair of city indices i, j:
#       pheromones[i][j] = (1 - rho) * pheromones[i][j]
#
# Then apply deposits from every ant:
#   for each (tour, length) in tours_with_lengths:
#       deposit = q / length
#       for each city in tour:
#           next_city = city after it, wrapping last city to first
#           pheromones[city][next_city] += deposit
#           pheromones[next_city][city] += deposit
#
# The two updates keep the matrix symmetric for an undirected TSP. Do not
# deposit on diagonal entries (an edge from a city to itself).
#
# Pseudocode function:
#   update_pheromones(pheromones, tours_with_lengths, config):
#       evaporate every entry
#       add each ant's deposit to each edge it used and the reverse edge
#

def update_pheromones(pheromones, tours_with_lengths, config, symmetric=True):
    # Evaporation
    for i in range(len(pheromones)):
        for j in range(len(pheromones)):
            pheromones[i][j] *= (1 - config.rho)

    # Deposits
    for tour, length in tours_with_lengths:
        deposit = config.q / length
        for index, city in enumerate(tour):
            next_city = tour[(index + 1) % len(tour)]
            pheromones[city][next_city] += deposit
            if symmetric:
                pheromones[next_city][city] += deposit

#
# STEP 5 — Coordinate a complete solver run
# ------------------------------------------
# Public function concept:
#   solve(cities, config=None, seed=None) -> result
#
# Pseudocode:
#   if config was not provided:
#       create configuration with defaults
#
#   distances = tsp.distance_matrix(cities)
#   city_count = number of cities
#   if config.ants is 0:
#       ant_count = city_count
#   otherwise:
#       ant_count = config.ants
#
#   create a random-number generator from seed
#   initialize every pheromone edge to 1.0
#   set each diagonal pheromone value to 0.0
#   best_tour = none
#   best_length = infinity
#   history = empty list
#
#   repeat config.iterations times:
#       tours_with_lengths = empty list
#
#       repeat ant_count times:
#           tour = build_tour(...)
#           length = tsp.tour_length(tour, distances)
#           add (tour, length) to tours_with_lengths
#
#           if length is less than best_length:
#               best_tour = tour
#               best_length = length
#
#       update_pheromones(pheromones, tours_with_lengths, config)
#       append best_length to history
#
#   return a result containing best_tour, best_length, and history
#

def solve(cities, config=None, seed=None):
    if config is None:
        config = Config()

    distances = distance_matrix(cities)
    return _solve_with_distances(
        distances,
        config=config,
        seed=seed,
        symmetric_pheromones=True,
    )


def solve_distance_matrix(cost_matrix, config=None, seed=None):
    """Solve TSP using caller-supplied directed costs instead of coordinates.

    Matrix rows and columns must use the same city ordering. Off-diagonal costs
    must be finite and positive; diagonal entries must be zero. Asymmetric
    costs are supported for one-way roads.
    """
    if config is None:
        config = Config()
    distances = validate_distance_matrix(cost_matrix)
    return _solve_with_distances(
        distances,
        config=config,
        seed=seed,
        symmetric_pheromones=False,
    )


def _solve_with_distances(distances, config, seed, symmetric_pheromones):
    city_count = len(distances)
    ant_count = city_count if config.ants == 0 else config.ants

    rng = random.Random(seed)
    pheromones = [[1.0 if i != j else 0.0 for j in range(city_count)] for i in range(city_count)]

    best_tour = None
    best_length = float('inf')
    history = []
    tour_history = []

    for _ in range(config.iterations):
        tours_with_lengths = []

        for _ in range(ant_count):
            tour = build_tour(city_count, pheromones, distances, config, rng)
            length = tour_length(tour, distances)
            tours_with_lengths.append((tour, length))

            if length < best_length:
                best_tour = tour
                best_length = length

        update_pheromones(
            pheromones,
            tours_with_lengths,
            config,
            symmetric=symmetric_pheromones,
        )
        history.append(best_length)
        tour_history.append(tuple(best_tour))

    return Result(
        best_tour=best_tour,
        best_length=best_length,
        history=history,
        tour_history=tour_history,
    )

# STEP 6 — Implement and test one piece at a time
# ------------------------------------------------
# 1. Define the configuration and result types.
# 2. Implement and test choose_next_city: it only returns unvisited cities.
# 3. Implement and test build_tour: it visits every city exactly once.
# 4. Implement and test update_pheromones: evaporation and deposits are correct.
# 5. Implement solve and test it with a small square from tsp.py.
# 6. Run twice with the same seed and confirm the results match.
# 7. Confirm history never increases; it stores the best-so-far distance.
