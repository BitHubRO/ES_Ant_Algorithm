# Visualization Build Checklist

This checklist is for the **road-map TSP visualization** described in
[ROAD_MAP_GUIDE.md](ROAD_MAP_GUIDE.md). Check an item only after implementing
and verifying it. Keep algorithm changes in `algorithm/` and agree on
interfaces with the algorithm owner.

## Scope and design

- [ ] Confirm the assignment permits a road-distance TSP version.
- [ ] Confirm the app visits multiple stops and returns to the first stop.
- [ ] Agree on the solver's cost-matrix input and result format.
- [ ] Choose a travel objective (distance or travel time) and travel mode.
- [ ] Choose a map display source and road-routing source.
- [ ] Check current usage, caching, attribution, key, and rate-limit rules.
- [ ] Define error behavior for offline access and unreachable road legs.

## Map shell and stops

- [ ] Create the window layout and map display area.
- [ ] Display a small fixed map area with required attribution.
- [ ] Add numbered stop markers from a fixed coordinate list.
- [ ] Support selecting stops on the map.
- [ ] Add remove-stop and clear-stops actions.
- [ ] Validate geographic coordinates and duplicate stops.
- [ ] Keep stable stop IDs through optimization and display.
- [ ] Fit/zoom the map to show all selected stops.

## Road costs and solver connection

- [ ] Define a provider-independent distance-matrix interface.
- [ ] Return an `n × n` cost matrix and set self-costs to zero.
- [ ] Keep directionality when one-way routes make costs asymmetric.
- [ ] Validate costs for missing, negative, non-finite, or unreachable entries.
- [ ] Add cache behavior and invalidate it when stops or mode change.
- [ ] Adapt the algorithm API to accept a caller-supplied cost matrix.
- [ ] Ensure ACO selection and tour scoring both use the road-cost matrix.
- [ ] Adapt nearest-neighbor baseline to the same matrix.
- [ ] Compare ACO and baseline on identical stops/costs.

## Road geometry and results

- [ ] Fetch geometry for every ordered leg of the returned tour.
- [ ] Include the return leg from last stop to first.
- [ ] Validate each geometry's endpoints and reported cost.
- [ ] Draw street polylines in route order; never replace a failed leg with a
      straight line without clearly warning the user.
- [ ] Label stops with visit order and distinguish the start stop.
- [ ] Display the order, total cost, and unit.
- [ ] Display ACO parameters and seed for reproducibility.

## Reliability and verification

- [ ] Use fake deterministic road data for UI and integration tests.
- [ ] Test asymmetric and unreachable matrix cases.
- [ ] Test missing/malformed responses, timeout, rate limit, and cancellation.
- [ ] Keep the UI responsive during network and solver work.
- [ ] Ensure stale requests cannot overwrite newer stop selections.
- [ ] Verify required provider attribution remains visible.
- [ ] Test a small real map area with a small number of stops.
- [ ] Prepare a preconfigured demo and offline backup.
