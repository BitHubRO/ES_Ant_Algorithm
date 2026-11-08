"""Background solver work. This module never reads or updates Tkinter widgets."""

from queue import Queue
from threading import Event

from algorithm.aco import Config, IterationProgress, Result, solve, solve_distance_matrix
from algorithm.tsp import City
from .geography import geographic_distance_matrix
from algorithm.comparison import ComparisonFinished, compare_distance_matrix
from algorithm.tsp import distance_matrix


def run_solver(cities: tuple[City, ...], config: Config, seed: int,
               messages: Queue[Result | IterationProgress | Exception], *, geographic: bool = False,
               live_updates: bool = False, iteration_delay: float = 0.0,
               cancel_event: Event | None = None, record_pheromones: bool = False) -> None:
    """Deliver either a result or an error to the GUI thread."""
    cancel = cancel_event if cancel_event is not None else Event()

    def report(progress):
        if cancel.is_set():
            raise InterruptedError("Run stopped.")
        if live_updates:
            messages.put(progress)
        # Waiting happens in the worker, so Tkinter can render the new point.
        # No delay after the last iteration; Event.wait also lets close stop work.
        if progress.iteration < progress.total_iterations and iteration_delay > 0:
            if cancel.wait(iteration_delay):
                raise InterruptedError("Run stopped.")

    try:
        if geographic:
            messages.put(solve_distance_matrix(geographic_distance_matrix(cities), config, seed=seed,
                                              progress_callback=report, record_pheromones=record_pheromones))
        else:
            messages.put(solve(cities, config, seed=seed, progress_callback=report,
                               record_pheromones=record_pheromones))
    except Exception as error:
        messages.put(error)


def run_comparison(cities, config, seed, messages, *, geographic=False, live_updates=False,
                   iteration_delay=0.0, cancel_event=None, record_pheromones=False):
    """Build costs once and run each method in the same background worker."""
    cancel = cancel_event if cancel_event is not None else Event()

    def check_cancel():
        if cancel.is_set():
            raise InterruptedError("Comparison stopped.")

    def report(event):
        check_cancel()
        if event.state != "progress" or live_updates:
            messages.put(event)
        if (event.progress is not None and event.progress.iteration < event.progress.total_iterations
                and iteration_delay > 0 and cancel.wait(iteration_delay)):
            raise InterruptedError("Comparison stopped.")

    try:
        costs = geographic_distance_matrix(cities) if geographic else distance_matrix(cities)
        reports = compare_distance_matrix(costs, config, seed, symmetric_pheromones=not geographic,
                                          callback=report, cancel_check=check_cancel,
                                          record_pheromones=record_pheromones)
        messages.put(ComparisonFinished(reports))
    except Exception as error:
        messages.put(error)
