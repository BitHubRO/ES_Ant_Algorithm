# Team Checklist

Use this list to track your own implementation. The tutorials are instructions,
not completed features. Check boxes only after your team has implemented and
verified the item.

## Decisions and collaboration

- [ ] Confirm with the instructor that TSP is an acceptable problem.
- [ ] Agree on Python and Tkinter (or record the team's alternative).
- [ ] Set up repository collaboration and a simple branch/review workflow.
- [ ] Agree on the solver input/output interface before parallel implementation.
- [ ] Assign an algorithm owner and a visualization owner.

## Algorithm — follow [algorithm/TUTORIAL.md](algorithm/TUTORIAL.md)

- [x] Represent city coordinates and calculate the distance matrix.
- [ ] Calculate closed-tour length and verify the square example by hand (code/tests complete; team hand-check remains).
- [x] Define ACO parameters and result format.
- [x] Implement probabilistic selection among unvisited cities.
- [x] Build complete tours and calculate their lengths.
- [x] Add evaporation and pheromone deposits.
- [x] Track best-so-far tour and history.
- [x] Test invalid inputs, repeatability, and small instances.
- [x] Implement nearest-neighbor baseline.
- [x] Implement budget-matched random search and three-method GUI comparison.
- [x] Add repeated-seed comparison summaries and CSV export with reproducibility metadata.
- [ ] Run repeated experiments on 10, 30, and 50+ cities.
- [ ] Compare alpha, beta, and rho one at a time; report average and best.
- [ ] Implement one or two extensions (elitist or Max-Min).
- [ ] Save experiment results and produce tables/graphs.

## Visualization — follow [visualization/TUTORIAL.md](visualization/TUTORIAL.md)

- [x] Create the window layout with controls, city canvas, and results area.
- [x] Generate or define cities and draw labeled markers.
- [x] Draw the returned best tour, including its closing edge.
- [x] Add and validate alpha, beta, rho, ant, and iteration inputs.
- [x] Wire Start and Reset to the agreed solver interface.
- [x] Display best distance and convergence history.
- [ ] Add click-to-place cities or file loading if time permits.
- [x] Add animation or pheromone styling if time permits.
- [x] Add CSV export if time permits.
- [ ] Test the demo and capture a backup recording/screenshots.

## Presentation and delivery

- [ ] Prepare 10–12 slides: problem, inspiration, steps, formulas, parameters,
      architecture, demo, experiments, comparison, limitations, conclusions.
- [ ] Finish the README with final implementation and run instructions.
- [ ] Ensure both teammates can explain each formula and the full application.
- [ ] Finish implementation by 8 November; reserve 9–10 November for buffer and
      final rehearsal.

## Suggested schedule

| Dates | Goal |
| --- | --- |
| 22–25 October | Confirm scope, set up the shared repo, implement city/distance foundation |
| 26 October–1 November | Implement and test core ACO, then connect visualization |
| 2–5 November | Run experiments, implement extensions, fix bugs |
| 6–8 November | Finish presentation, documentation, and demo practice |
| 9–10 November | Buffer and final rehearsal |
