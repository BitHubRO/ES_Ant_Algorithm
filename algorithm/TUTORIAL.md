# Algorithm Tutorial: Build the ACO Solver

This guide walks you through implementing the algorithm yourself. It describes
what each module should do and how to verify it without providing a finished
solver.

## 1. Define the problem and the data

Use the Traveling Salesperson Problem (TSP): visit each city exactly once and
return to the starting city while minimizing total distance.

Start with a small set of 2D coordinates. Treat each city as an integer index
into the coordinate list. A tour such as `[2, 0, 1]` means travel from city 2
to city 0, then city 1, and finally back to city 2. Do not append the starting
city a second time; include the closing edge when calculating the length.

Suggested implementation file: `algorithm/tsp.py`.

Implement and test these operations first:

1. **`distance_matrix(cities)`:** for every pair `(i, j)`, calculate Euclidean distance:
   `d(i,j) = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)`.
   Return a square matrix where `distances[i][j]` is the distance from city
   `i` to city `j`.
2. **`tour_length(tour, distances)`:** add the distance from each city to the
   next, including the last-to-first edge. The tour is a sequence of city
   indices, with the starting city not repeated at the end.
3. **Input validation:** require at least two cities and distinct coordinates
   for this first version. The tour must contain each city index exactly once.

Check by hand that four points at the corners of a unit square have a perimeter
tour length of 4.

## 2. Choose a small solver interface

Before splitting work, agree on one interface. For example, the UI should be
able to call a function conceptually like:

```text
solve(cities, parameters, seed) -> best tour, best length, history
```

The `cities` input is a sequence of coordinates. `parameters` contains alpha,
beta, evaporation rate rho, deposit amount Q, ant count, and iteration count.
The result contains city indices for the best tour, its length, and the best
length after each iteration. Keep UI code out of this module.

For road-based costs, use `solve_distance_matrix(cost_matrix, config, seed)`
instead. It accepts a square directed matrix in which each off-diagonal value
is a positive finite cost and each diagonal value is zero. Rows and columns
must use the same stop ordering. This supports one-way roads where
`cost[i][j]` may differ from `cost[j][i]`. Its matching baseline is
`nearest_neighbor_distance_matrix(cost_matrix)`. Neither function fetches map
data or route geometry; the visualization layer supplies costs and separately
gets street geometry for drawing.

Suggested implementation file: `algorithm/aco.py`. Define a parameter type and
a result type before implementing the main loop. Pick and document consistent
parameter names with your teammate.

## 3. Understand the ant's next-city choice

Each ant starts at a randomly chosen city. At each step, it chooses only from
cities it has not visited yet. The desirability of candidate city `j` from
current city `i` is:

```text
weight(i,j) = pheromone(i,j)^alpha * (1 / distance(i,j))^beta
probability(i,j) = weight(i,j) / sum(weight(i,k) for unvisited k)
```

- `alpha` controls how strongly previous pheromone influences choices.
- `beta` controls preference for short edges.
- `pheromone` begins at a small positive constant, such as 1.
- `1 / distance` is the heuristic value; reject duplicate coordinates so it
  never divides by zero.

Implement roulette-wheel selection: draw a random number in `[0, sum(weights))`
and select the first candidate whose cumulative weight reaches that number.
Using a seeded random-number generator makes debugging and comparisons
reproducible.

Test this piece separately: selected cities must always be unvisited, and
repeating a fixed seed should repeat the same choices.

## 4. Build complete tours

For each ant:

1. Pick a start city and mark it visited.
2. Repeatedly choose a next city from the unvisited set.
3. Stop when every city is visited.
4. Calculate the closed-tour length, including the edge back to the start.

At the end, verify that a tour has exactly one occurrence of every city index.
Test this before implementing pheromone updates.

## 5. Add pheromone updates and the iteration loop

For every iteration:

1. Have each ant build a tour and calculate its length.
2. Update the best-so-far tour if any ant improved it.
3. Evaporate pheromone on every edge:
   `pheromone(i,j) = (1 - rho) * pheromone(i,j)`.
4. For every ant tour, deposit `Q / tour_length` on each edge it traversed.
5. Record the best-so-far length in the history.

The TSP graph is undirected, so decide whether to store a symmetric matrix. If
so, every deposit to edge `(i,j)` must also update `(j,i)`. Do not deposit on
self-edges. Keep rho between 0 and 1 and use positive Q.

Start with `alpha = 1`, `beta = 3`, `rho = 0.4`, `Q = 100`, one ant per city,
and 100–200 iterations. These are starting values to experiment with, not
guaranteed optimal settings.

## 6. Test the solver before connecting the UI

Suggested test file: `algorithm/test_aco.py` (or a `tests/` folder if you
prefer standard test discovery).

Test at least:

- A tour visits each city exactly once and includes the closing edge in length.
- The square example has a best possible length of 4.
- The best-so-far history never increases.
- Fixed seeds produce repeatable results.
- Invalid inputs and parameter values produce a clear error.
- The solver works for 2, 3, and a modest number of cities.

ACO is randomized and generally does not prove optimality. Avoid tests that
expect one exact tour except when using a fixed seed. Prefer checking valid
tours, reproducibility, and known lower bounds.

## 7. Add a nearest-neighbor baseline

Implement a separate baseline, not a special case hidden in the ACO loop:

1. Start from a chosen city.
2. Repeatedly go to the closest unvisited city.
3. Close the tour and calculate its length.

Try every possible starting city and keep the shortest nearest-neighbor result.
This is a heuristic comparison, not a guaranteed optimum. Compare its length
with ACO on the exact same city sets.

Optional for very small city counts: implement brute force to verify the
optimum, but limit it to small instances because the number of tours grows
factorially.

## 8. Run fair experiments

Suggested implementation file: `algorithm/experiments.py`.

1. Generate or define fixed city sets of 10, 30, and 50+ cities.
2. Run each parameter setting 5–10 times using different seeds.
3. Change only one of alpha, beta, or rho at a time.
4. Record the ACO best and average tour length, plus nearest-neighbor length.
5. Keep the city sets and seeds consistent when comparing settings.
6. Save results in a simple CSV with columns for city count, parameters, seed,
   method, and tour length.

Report averages and best results. One unusually good random run is not enough
to establish that a parameter setting is better.

## 9. Choose one or two extensions

Only start after the basic solver and baseline work:

- **Elitist Ant System:** deposit additional pheromone on the best-so-far tour
  each iteration. Make the extra deposit amount explicit and compare results.
- **Max-Min Ant System:** clamp pheromone values to chosen minimum and maximum
  bounds after updates. Explain how the bounds affect exploration.

Add tests and compare the extension to the basic version with repeated runs.
Avoid changing several algorithm rules at once; otherwise, it is hard to tell
which change affected the result.

## 10. Suggested algorithm folder as you grow the project

```text
algorithm/
  TUTORIAL.md
  tsp.py             City distances and tour length
  aco.py             Parameters, ant construction, and solver
  baselines.py       Nearest-neighbor and optional brute force
  experiments.py    Repeated runs and CSV output
  test_aco.py        Solver and edge-case tests
```

Create these code files as you reach their tutorial sections; they are not
pre-written. Coordinate the solver interface with the visualization owner
before either side depends on it.
