# Ant Colony Optimization Project

This project implements Ant Colony Optimization for the Traveling Salesperson
Problem, with an interactive Tkinter application, an offline Romania map,
algorithm comparisons, tests, and reproducible experiments. The tutorials explain
the implementation and describe optional extensions.

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

## Project layout

```text
algorithm/
  aco.py              ACO solver and optional progress/pheromone snapshots
  tsp.py              Distance matrices and closed-tour scoring
  baselines.py        All-start nearest neighbor and random search
  comparison.py       Shared-cost, matched-budget comparison engine
  comparison_export.py CSV export and repeated-trial summaries
  compare.py          Repeated comparison command
  experiments.py      ACO parameter-sweep experiments
visualization/
  app.py              Interactive comparison application
  runner.py           Background solver/comparison workers
  comparison_plot.py  Common-scale comparison graph
  pheromone_view.py    Pheromone heatmap
  geography.py        Offline data and geographic costs
  romania_map.py      County boundaries and selectable city markers
  data/               Bundled Romania data and attribution
tests/                Automated checks
results/              Saved experiment CSVs
```

The solver is independent from the UI and can be tested without opening a window.

## Open the new application window

From the repository root, run:

```powershell
python -m visualization.app
```

The window provides a dataset selector, parameter fields, settings validation,
Reset form, and random city generation. Choose Random cities, set the count
and seed, and click Generate cities to draw numbered markers. The same count
and seed reproduce the same coordinates; resizing only changes their display.
Press **Run all 3** to compare ACO, nearest neighbor (all starts), and random
search on one shared distance matrix. A background worker runs them sequentially;
city/parameter controls are locked until the comparison finishes. The table shows
best cost, compute time, tours evaluated, and status. Lowest-cost rows are
highlighted, including ties. A negative ACO improvement means nearest neighbor
found the shorter route. Click a row or use Show route to inspect its closed
tour. Route colors are blue for ACO, green for nearest neighbor, and purple
for random search; orange still marks the start city.

The graph uses **tours evaluated** on the horizontal axis: ACO and random search
have equal budgets of effective ants × iterations. Random search generates shuffled
tours and keeps its best, including duplicate samples. Nearest neighbor constructs
one greedy tour per starting city and appears as a dashed cost reference, not
an invented iteration curve. All methods include the return edge and use the
same units. Equal tour counts do not imply equal computational work.

Compute times exclude shared matrix setup, GUI work, artificial waits, and ACO
pheromone snapshot copying. They include core search and best-tour bookkeeping.
Enable **Slow live run** before Run all 3 and choose a delay (100, 300, or
700 ms) to watch the best-so-far cost line and route update during computation.
The delay is added between completed iterations, so expensive iterations can
take longer than that. The graph's x axis stays fixed at the total requested
iterations and fills from left to right. Slow mode is off by default; normal
runs publish each method's result when complete. Closing the window interrupts the
worker's delay and stops it at an iteration boundary.

After completion, the full cost history remains available for inspection.
The iteration slider follows ACO checkpoints; random search shows its best route
at the same evaluated-tour budget and nearest neighbor shows its final route.
The **Route details** tab lists the currently selected route's visiting order.
Enable **Animate iterations (replay)**
to automatically play those snapshots after computation finishes. Animation
is off by default. Play/Pause controls playback; the speed selector sets the
delay between iterations. Moving the slider pauses playback. Pressing Play
at the end replays from iteration 1. Unchecking the option stops playback.
The animation shows the best-so-far tour, not individual ants or pheromones;
consecutive iterations may show the same route when no improvement occurs.
Rerun with different parameters on the
same loaded cities for comparison. The seed field controls solver randomness;
it changes city coordinates only when you click Generate cities.
Reset form clears cities and results and restores defaults. Random city labels
start at 0 to match the solver's indices. The US state-capital dataset is not
loaded yet.
The window uses Tkinter and needs no extra pip packages.
The map and Results panels sit side by side, sharing a draggable vertical
divider. Move it left or right to adjust their widths. Both panels use the full
available height so enlarging the map does not collapse the analysis canvases.
Geographic proportions are preserved as the canvas resizes.

**Export CSV** saves the three summary rows plus checkpoint histories. The file
includes original run settings, seed, units, selected-city coordinates and names,
tour indices, costs, counts, and compute times. Editing input fields after a run
does not change its exported metadata. Only ACO has a pheromone matrix.

## Repeat comparisons across seeds

Use a fixed city set and several solver seeds to compare typical results:

```powershell
python -m algorithm.compare --cities 30 --seeds 7,8,9,10,11 --iterations 100
```

This writes `results/comparison/trials.csv` (summaries and convergence histories)
and `results/comparison/summary.csv` (mean, best, worst, sample standard deviation,
and mean compute time). All trials use the same cities generated with city seed
2026; use `--city-seed` to change the problem and `--output-dir` to choose another
output folder. Nearest neighbor is deterministic, so its cost repeats across
seeds. Stochastic variation applies to ACO and random search. Existing files in
the chosen output directory are replaced. Run `--help` for parameter options.

### Inspect pheromones

The Results area has **Cost evolution** and **Pheromone matrix** tabs.
Recording is enabled by default in the GUI. Open the matrix tab, then use
Slow live run to watch pheromones change during computation. After completion,
the shared iteration slider and replay select matching cost, route, and matrix
snapshots. Each snapshot is taken after evaporation and all ants' deposits.

Rows are source cities and columns are destination cities. Random-city labels
are indices; Romania labels are county codes for the selected cities only.
Hover a cell for full city names and the stored pheromone value. Gray diagonal
cells are unused. Light blue means weaker pheromone and dark blue means stronger.
Use the scrollbars for larger matrices. Log(1 + pheromone) coloring is enabled
by default; uncheck it for a linear scale. The legend shows numerical endpoints.
Its upper bound grows with the largest value observed during a live run; after
completion the same bound is used for every saved iteration.

Uncheck **Record pheromone history for the next run** to avoid storing matrices.
Storage grows with iterations × cities²; the GUI limits recording to 5,000,000
matrix cells per run. Reduce the city/iteration counts or disable recording for
larger runs. Command-line solver calls do not record matrices by default; pass
`record_pheromones=True` to `solve` or `solve_distance_matrix` to opt in.
Tour rotation for a selected starting city never reorders matrix rows/columns.

### Select Romania county seats

Choose **Romania - county seats** to load an offline county map and 41 distinct
county-seat locations. Click a marker to select or deselect it; hover to see
the city and county name. Markers are labeled with county codes. White means
unselected, blue means selected, and orange marks the displayed tour's start.
București appears once, representing Ilfov's seat and the capital.

Choose at least two cities, or use Select all, then press Start. Clear selection
removes all chosen cities. Changing the selection clears the previous result
and stops playback. Selection is locked during computation. The result includes
the city names in visit order and the closing return leg. Replay works with
the selected cities exactly as it does with random cities.

The first city you select is the starting city. It is marked orange immediately
and named above the map. The final route and every replay iteration start and
end there. If you deselect it, the earliest remaining selected city becomes
the start; selecting a city again puts it last in the selection order.
Select all preserves an existing starting city. If nothing was selected,
Select all chooses Alba Iulia (the first city in dataset order). Clear selection,
Reset form, and switching datasets clear the starting-city choice.
ACO still explores tours with random starting cities; the saved closed tours
are rotated for display, preserving their edges, direction, and distances.

Distances are **geographic kilometers**, calculated with Haversine from city
coordinates, not driving distances. Route lines connect cities directly and
do not follow roads. The map keeps its full-country extent when you select
fewer cities or resize. No network or API key is required at runtime.
Data attribution and source details are in [visualization/data/SOURCES.md](visualization/data/SOURCES.md).

GUI data and solver-integration checks can run without extra packages:

```powershell
python -m unittest discover -s tests -p "test_city_datasets.py" -v
python -m unittest discover -s tests -p "test_explorer_run.py" -v
python -m unittest discover -s tests -p "test_romania.py" -v
python -m unittest discover -s tests -p "test_live_progress.py" -v
python -m unittest discover -s tests -p "test_pheromones.py" -v
python -m unittest discover -s tests -p "test_comparison.py" -v
```

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
