# Visualization Tutorial: Build the Application

This guide describes how to build the app around your own solver. The first
sections help you build a simple working TSP display; a road-map-style version
is a later extension with different data and integration needs.

Start with [ROAD_MAP_GUIDE.md](ROAD_MAP_GUIDE.md) for the end-to-end design of a
real-world road-map TSP app, including road-distance matrices and route
geometry. Use [BUILD_CHECKLIST.md](BUILD_CHECKLIST.md) to track the work.

The current ACO solver solves TSP over coordinate distances. A road-map version
must use road-network distances between stops, and must fetch or calculate
street geometry to draw the selected legs. A map background by itself does not
make routes follow roads.

## 1. Agree on the interface first

Before drawing screens, agree with the algorithm owner on:

- How city coordinates are represented.
- The names and defaults for alpha, beta, rho, Q, ants, and iterations.
- How the solver is called.
- The shape of its result: best city-index tour, best distance, and best-length
  history.
- How validation errors are reported.

The UI should not reimplement ant selection or pheromone updates. Its job is to
collect inputs, call the solver, and present results.

## 2. Create a window and separate responsibilities

Suggested first file: `visualization/app.py`. Begin with a Tkinter window and
divide it into:

1. **Controls:** parameter inputs and Start/Reset buttons.
2. **City canvas:** dots for cities and lines for the best tour.
3. **Results area:** best distance, run status, and convergence graph.

Keep drawing helpers separate from button callbacks when the file grows. The
canvas should receive coordinates and a tour to display; it should not own ACO
state.

Suggested folder once you add files:

```text
visualization/
  TUTORIAL.md             Basic UI and drawing guide
  ROAD_MAP_GUIDE.md       Road-network data and map integration guide
  BUILD_CHECKLIST.md      Ordered implementation and verification checklist
  app.py                  Window and control wiring
  map_view.py             Map display and map coordinate conversion
  stop_selection.py      Stop markers and user-selected locations
  route_data.py           Distance matrix and route-geometry access
  drawing.py              Stop and road-route rendering
  test_visualization.py   UI-independent map and route data tests
```

## 3. Decide how cities enter the app

Start with a fixed example list or generate random points when the app starts.
This makes it possible to build the drawing before the full algorithm is ready.

Then add city creation:

- Store the canvas coordinates separately from normalized solver coordinates.
- On click, convert the canvas position into the solver's coordinate range.
- Give every city a stable index; the solver returns indices that refer to this
  exact list.
- Provide a way to clear or regenerate the cities.

Nice-to-have later: load coordinates from a text/CSV file. Validate the file
and show a user-visible error for malformed or insufficient data.

## 4. Draw cities and the tour

Implement rendering in small steps:

1. Clear the canvas before drawing a new result.
2. Draw each city as a visible marker and label it with its index.
3. Convert solver coordinates to canvas coordinates. Invert the vertical axis
   if needed, because screen y commonly increases downward.
4. Draw a line between each consecutive city in the best tour.
5. Draw the final line from the last city back to the first.
6. Redraw cities on top of the lines so markers remain visible.

Use one coordinate transform for both dots and lines. Test with a square tour:
the drawn edges should form a closed loop, with no missing return edge.

Do not try to display every possible pheromone edge at first. A complete graph
can become visually cluttered. Start by showing only the current best tour.

## 5. Add parameter controls

Provide labeled input fields for:

- Alpha (`alpha`): pheromone influence.
- Beta (`beta`): distance heuristic influence.
- Rho (`rho`): evaporation rate, strictly between 0 and 1.
- Ant count: positive integer; a useful default is the number of cities.
- Iterations: positive integer.
- Q: positive pheromone deposit amount (include if the team wants it adjustable).

When Start is clicked, parse and validate all inputs before starting the solver.
Show a clear error beside the controls or in a dialog; do not silently replace
invalid values with defaults.

## 6. Connect the Start and Reset actions

The Start callback should:

1. Verify that enough cities exist.
2. Read and validate the fields.
3. Disable or otherwise guard against duplicate runs.
4. Call the solver using the agreed interface.
5. Display the best tour, best distance, and history from the returned result.
6. Re-enable controls when the run completes, even if an error occurred.

For a modest problem size, a direct call may be adequate. If the window freezes
for large runs, run computation away from the Tkinter event loop and send
results back safely. Tkinter UI updates must happen on the UI thread. First
build the simpler synchronous version; add background execution only if you
observe freezing.

Reset should clear or restore the chosen city set, remove previous tour lines,
clear result labels and graph data, and return controls to a usable state.
Decide whether Reset restores the original generated cities or empties the
canvas, and make the button label/behavior clear.

## 7. Show convergence

The solver history contains the best-so-far length after each iteration. Plot
iteration number on the horizontal axis and best distance on the vertical axis.

Start with a simple line drawn on a second Tkinter canvas. If the team chooses
Matplotlib instead, add it as a dependency and embed its figure in the Tkinter
window. Label both axes and redraw the graph after a run. The curve should be
flat or decreasing because it tracks best-so-far, not the current iteration's
worst or average tour.

## 8. Optional animation and pheromone display

Once the basic interface works:

- To animate progress, adjust the solver/app interface to report selected
  progress snapshots or best-so-far updates.
- Schedule UI redraws through Tkinter's event scheduling instead of blocking
  the event loop.
- If visualizing pheromone, map larger values to darker or thicker edges, and
  include a scale/legend.
- Limit how many edges are drawn or use a threshold so the canvas remains
  readable.

Animation is optional. A clear final tour and convergence plot are more
important than a flashy but unreliable demo.

## 9. Save results and support a demo

Add CSV export after experiment output is defined with the algorithm owner.
Include the city count, parameters, seed if used, best length, and method.
Handle file errors visibly.

For the presentation, prepare a known small city set and parameter preset so
the demo starts quickly. Save screenshots or record a short backup demo in
case the live run fails.

## 10. Verify the UI

Manually check:

- The window opens and can be closed normally.
- City markers and labels appear at the expected positions.
- The tour connects indices in the returned order and closes its loop.
- Invalid parameter text produces a clear error instead of crashing.
- Start and Reset work repeatedly.
- The displayed distance matches the solver result.
- The convergence graph uses the history in the correct order.
- A larger run does not leave the window permanently unresponsive.
- The demo works with the exact environment used for the presentation.

For the road-based extension, continue with [ROAD_MAP_GUIDE.md](ROAD_MAP_GUIDE.md)
instead of trying to make the simple canvas draw pretend street routes.
