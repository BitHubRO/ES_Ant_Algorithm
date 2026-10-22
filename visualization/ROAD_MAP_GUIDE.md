# Road-Map TSP Application Guide

This guide explains how to extend the project into a TSP application displayed
on a real-world-style street map. It is an implementation guide, not finished
code. Build the parts in the order below and coordinate the solver interface
with the algorithm owner.

## 1. Confirm what problem the app solves

This project is TSP: select several stops, visit every stop exactly once, and
return to the starting stop. It is not a two-point shortest-path finder.

The app should let a user select at least three stops (four or more makes a
clear demo), calculate a good visit order, draw the road-following leg between
each pair of consecutive stops, and return from the final stop to the first.
The order is optimized approximately by ACO; each individual leg follows the
road network.

## 2. Understand the four kinds of map data

Keep these concepts separate in the design:

1. **Map display:** map tiles or a rendered map that provide visual context.
2. **Stop coordinates:** geographic longitude and latitude for each selected
   stop.
3. **Road-cost matrix:** driving/walking distances or travel times between
   every pair of stops. The ACO solver uses this matrix to choose a visit order.
4. **Leg geometry:** the sequence of geographic points describing the actual
   streets for one route from stop A to stop B. The map draws these points.

Map tiles are not a routable road graph. A straight line between markers is
also not a road route. Do not use the display map to infer route costs or street
geometry.

## 3. Select a suitable map and routing source

Before coding, decide how the app will obtain the display map and road data.
Possible approaches include a permitted routing service, a permitted map
rendering service, or a downloaded road-network dataset and local routing
engine.

Check each chosen source's current terms before use:

- Is use allowed for a student demo and the expected number of requests?
- Is a key or account required?
- What request limits, caching rules, and attribution are required?
- Are bulk matrix requests permitted, or must the app request pairs separately?
- Which travel mode is supported (driving, walking, cycling)?
- Does the response include both distance/time and route geometry?
- What should the UI do when the network is unavailable or a request fails?

Do not embed private API keys in source control. Do not assume a public tile
server is an unrestricted production service. Keep required copyright/provider
attribution visible in the app.

Keep the provider behind a small interface so the UI and solver do not depend
on provider-specific response formats. Conceptually, the app needs operations
like:

```text
get_distance_matrix(stops, travel_mode) -> matrix
get_leg_geometry(start_stop, end_stop, travel_mode) -> ordered coordinates
```

These are design contracts, not required function names. Normalize the
provider's responses into your own data types as soon as they arrive.

## 4. Choose the app structure

Keep display, user interaction, routing data, and optimization separate:

```text
visualization/
  app.py                 Window, controls, and application state
  map_view.py            Map display and map/canvas coordinate transforms
  stop_selection.py      Add, move, label, and remove stops
  route_data.py          Provider interface, matrix, leg geometry, caching
  route_drawing.py       Draw ordered road geometry and stop markers
  tests/
    test_stop_selection.py
    test_route_data.py
    test_route_drawing.py
```

Responsibilities:

- `app.py` coordinates events and displays errors/status. It should not parse a
  provider's raw JSON or implement ACO.
- `map_view.py` owns the visual map and screen projection. It does not compute
  the TSP visit order.
- `stop_selection.py` owns the selected stop list and stable stop IDs.
- `route_data.py` converts stop locations to a road-cost matrix and supplies
  leg geometry.
- `route_drawing.py` draws stop markers and the geometry for each ordered leg.
- The existing `algorithm/` code owns optimization and generic TSP logic.

## 5. Build a map-only shell first

Before connecting routing or ACO:

1. Make a window with a map display area, a control area, and a results area.
2. Show a map for one small, fixed geographic area.
3. Keep map attribution visible and readable.
4. Support zoom and pan if the selected map library provides these features.
5. Show a clear loading/error state if tiles fail to load.
6. Confirm that the map can be closed and reopened without leaving background
   tasks or hanging the app.

For an offline-first first version, use a small permitted local dataset. For an
online version, handle missing network access gracefully. Do not block the UI
thread while loading tiles.

## 6. Add and validate stops

For every selected stop, store:

- A stable ID or list index.
- Longitude and latitude in a documented order.
- An optional user-facing label.
- A display position only if needed by the map library.

Implement:

1. Click the map to add a stop, or provide an address/search control if you
   have a permitted geocoding source.
2. Display numbered markers in selection order.
3. Support removing a stop and clearing all stops.
4. Enforce a useful minimum and maximum number of stops for the demo.
5. Reject duplicate/near-identical stops or warn the user.
6. Validate geographic coordinate ranges:
   longitude is from -180 to 180; latitude is from -90 to 90.
7. Keep each stop's identity stable while sorting or drawing; the solver's
   returned indices must still refer to the same stop list.

Write tests for adding, removing, clearing, and retaining stop IDs. Test
coordinate-to-map conversion independently of the GUI.

## 7. Request the road-cost matrix

For `n` stops, the TSP solver needs an `n × n` matrix:

```text
cost[i][j] = road distance or travel time from stop i to stop j
cost[i][i] = 0
```

Implementation steps:

1. Choose one cost objective—distance or travel time—and label it in the UI.
2. Request road costs for each stop pair using the selected travel mode.
3. Normalize units, such as meters or seconds, consistently.
4. Validate that the response contains every required pair and finite
   non-negative costs.
5. Set diagonal costs to zero; do not treat unreachable legs as zero.
6. Preserve direction. One-way streets can mean `cost[i][j]` differs from
   `cost[j][i]`; do not force a symmetric matrix unless the data source and
   travel model justify it.
7. Cache results for the current stop set and travel mode to avoid repeated
   requests. Make cache invalidation clear when a stop or travel mode changes.
8. Surface timeouts, rate limits, unreachable legs, and malformed responses as
   clear errors. Do not silently fall back to straight-line distance.

### Coordinate with the algorithm owner

The algorithm now offers two entry points:

```text
solve(cities, config, seed) -> Euclidean-distance TSP result
solve_distance_matrix(cost_matrix, config, seed) -> matrix-cost TSP result
```

`solve_distance_matrix` accepts a complete directed matrix, so one-way road
costs may differ by direction. The matrix must be square, have a zero diagonal,
and positive finite costs between distinct stops. It uses the matrix both for
the ant's heuristic and for scoring tours, and it updates pheromone only on the
directed edges traversed. The existing `solve` keeps its Euclidean behavior and
symmetric pheromone updates.

The nearest-neighbor baseline also has a `nearest_neighbor_distance_matrix`
entry point. Use it with the exact same matrix to compare with ACO.

Test matrix-based solving with a small hand-built asymmetric matrix where the
best route is known. This catches assumptions that every edge has the same
cost in both directions. The matrix represents costs only; the visualization
still needs to retrieve route geometry separately in order to draw roads.

## 8. Optimize the stop order

Once the road-cost matrix is ready:

1. Validate the matrix before calling the solver.
2. Run ACO to find a TSP order of stop indices.
3. Keep the original stable stop list beside the result.
4. Show visit order, total cost, objective unit, settings, and run status.
5. Include a seeded run mode so the demo can be repeated.

Add a nearest-neighbor baseline that accepts the same matrix. Compare ACO and
the baseline on the same stops and same cost matrix. If the course requires an
exact small-instance reference, compare with brute force only for a very small
stop count.

## 9. Get road geometry for the chosen order

The optimized order identifies stop-to-stop legs; it does not contain the
street paths needed to draw them.

Given order `[s0, s1, ..., s(n-1)]`, request or retrieve geometry for:

```text
s0 -> s1
s1 -> s2
...
s(n-1) -> s0
```

For each leg:

1. Ask the routing source for a route using the same travel mode as the matrix.
2. Store the ordered route coordinates and reported distance/time.
3. Verify that returned geometry starts near the expected start and ends near
   the expected destination.
4. Preserve the leg order when combining geometries.
5. Avoid duplicating the shared endpoint when concatenating adjacent legs.
6. If a leg fails, report which pair could not be routed and do not draw a
   misleading straight connector.

Check that the sum of displayed leg costs is consistent with the matrix cost
for the selected order, allowing for provider rounding or route changes.

## 10. Draw the route and communicate its meaning

On the map:

- Draw every stop with its visit number, not only its original list index.
- Draw each road geometry polyline in visit order.
- Use a strong route color and a distinguishable start marker.
- Add a direction arrow or sequence labels if the map component supports them.
- Keep the map provider's attribution visible over the map.
- Fit the map to include all stops and the entire route.

Beside or below the map, show:

- Ordered stop labels.
- Total road distance or travel time and its unit.
- ACO parameters, random seed, and iteration count for reproducibility.
- Loading, success, and error status.

Do not present the ACO result as guaranteed optimal. Describe it as the best
tour found by the selected run.

## 11. Keep the interface responsive

Map tile requests, geocoding, matrix requests, and ACO runs may take time.

1. Disable duplicate Run actions while a request/run is active.
2. Show progress/status and provide Cancel if practical.
3. Perform network and CPU-heavy work outside the UI event loop.
4. Update widgets only through the UI framework's safe UI-thread mechanism.
5. Add request timeouts and handle cancellation.
6. Ignore stale responses if the user changed stops while a request was
   running.
7. On every success, failure, or cancellation, restore controls to a usable
   state.

Start with synchronous test doubles and a small stop count. Add background work
after the basic flow is correct.

## 12. Test with fake routing data before using a real provider

Create a small deterministic test graph or a fake provider that returns known
matrices and simple polylines. Test:

- A symmetric matrix, and an asymmetric matrix with one-way costs.
- A disconnected/unreachable stop pair.
- Missing pairs, invalid values, timeout, and malformed provider response.
- Stable mapping from solver indices back to the selected stop IDs.
- Correct retrieval of every ordered leg, including final return to start.
- Route geometry endpoints and leg concatenation.
- Total displayed route cost matching the solver's tour cost.
- Repeat runs with the same seed.
- UI loading, error, retry, and Reset behavior.

Only after these pass should you test a small real area. Use few stops to limit
requests and make failures easy to diagnose.

## 13. Recommended implementation milestones

1. Draw manually entered stops on a map canvas; no network routing yet.
2. Add a fake road-cost matrix and fake leg geometries.
3. Agree with the algorithm owner on matrix-based solver and baseline
   interfaces.
4. Show a complete route order and draw fake leg geometry.
5. Add automated tests for matrix, order, and display integration.
6. Select and verify permitted map and routing sources.
7. Add real road-cost requests with timeouts and caching.
8. Add real road geometries for the optimized legs.
9. Handle attribution, offline/error states, and demo rehearsal.

This sequencing lets you complete and present the interface even if external
map or routing services are temporarily unavailable.
