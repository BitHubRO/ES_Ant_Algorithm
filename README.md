# Ant Colony Optimization Project

This repository is a set of implementation tutorials, not a pre-built
application. Work through the topics, write the code yourselves, and use the
checklists to track progress.

## Start here

1. Read [algorithm/TUTORIAL.md](algorithm/TUTORIAL.md) to build and test the
   ACO solver for the Traveling Salesperson Problem (TSP).
2. Read [visualization/TUTORIAL.md](visualization/TUTORIAL.md) to build the
   application around your solver. For a road-map TSP version, continue with
   [visualization/ROAD_MAP_GUIDE.md](visualization/ROAD_MAP_GUIDE.md) and track
   tasks in [visualization/BUILD_CHECKLIST.md](visualization/BUILD_CHECKLIST.md).
3. Use [TODO.md](TODO.md) to divide and track the team work.

The tutorials use Python and recommend Tkinter for a simple desktop interface.
Before coding, confirm with your instructor that TSP is an acceptable problem.

## Suggested project layout

```text
algorithm/
  TUTORIAL.md       Guide for the solver, experiments, and algorithm tests
visualization/
  TUTORIAL.md       Basic UI, drawing, controls, and results display
  ROAD_MAP_GUIDE.md Real-world road-map TSP design and implementation guide
  BUILD_CHECKLIST.md Road-map visualization implementation checklist
TODO.md             Shared project checklist and schedule
```

As you implement the project, add your own Python modules and tests in the
folders described by each tutorial. Keep the ACO solver independent from the
UI so that it can be tested and run without opening a window.

## Run algorithm experiments

The experiment runner compares the ACO solver with nearest neighbor using fixed
city sets and seeds. It saves raw results and grouped summaries under
`results/`:

```powershell
.\.venv\Scripts\python.exe -m algorithm.experiments
```

The default run uses 10, 30, and 50 cities, seven ACO parameter settings, and
five seeds, and reports progress as it runs. Try a quick run first:

```powershell
.\.venv\Scripts\python.exe -m algorithm.experiments --city-counts 10 --seeds 11 --iterations 20
```

Use `--help` to see all options. You can also change `CITY_COUNTS`, `SEEDS`, and
`CITY_SEED` defaults in [algorithm/experiments.py](algorithm/experiments.py).

## Inspect one ACO tour

This small Tkinter script is an algorithm-side debugging aid, not the project's
visualization application:

```powershell
.\.venv\Scripts\python.exe -m algorithm.visualize_solution --cities 20 --iterations 100 --seed 7
```

It prints the best tour and opens a window showing the cities and closed route.
It also plots the best-so-far tour length after each iteration. Use the
iteration slider to move through the run: the map shows that iteration's
best-known route and the chart reports its distance. Close the window to exit.
To inspect the directed cost-matrix mode, run:

```powershell
.\.venv\Scripts\python.exe -m algorithm.visualize_solution --cost-mode matrix-demo --cities 10 --iterations 40 --seed 7
```

That mode uses synthetic directed costs and labels each selected edge with its
matrix cost. Its points and straight connecting lines are illustrative only;
they are not actual map locations or road geometry.

To try real driving costs and route geometry for four Cluj-Napoca landmarks:

```powershell
.\.venv\Scripts\python.exe -m algorithm.visualize_solution --cost-mode cluj-road --iterations 8
```

This requires internet access and calls the public OSRM demo server. The
iteration slider shows actual routed road geometry for each distinct
best-so-far tour snapshot fetched during the run. It is a small demo rather
than a production map service; it displays the route on a coordinate canvas
without background map tiles. The mode defaults to 8 iterations and allows at
most 12 to limit requests. For interactive maps or regular use, select a
provider and follow its current usage and attribution rules.

The algorithm also supports caller-provided directed cost matrices for future
road-based TSP work: use `solve_distance_matrix` and
`nearest_neighbor_distance_matrix` with the same matrix. Road route geometry
must still be obtained separately to draw actual streets.

Run the tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

## Suggested milestones

- **22–25 October:** agree on scope, make the repository collaborative, and
  implement the city model and distance calculations.
- **26 October–1 November:** finish the core solver, then connect the
  visualization.
- **2–5 November:** compare methods, run experiments, and complete an
  extension.
- **6–8 November:** prepare the README, presentation, and demo.
- **9–10 November:** reserve time for rehearsal and unexpected issues.

Aim to complete implementation by 8 November.
