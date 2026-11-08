"""Background solver work. This module never reads or updates Tkinter widgets."""

from queue import Queue

from algorithm.aco import Config, Result, solve, solve_distance_matrix
from algorithm.tsp import City
from .geography import geographic_distance_matrix


def run_solver(cities: tuple[City, ...], config: Config, seed: int,
               messages: Queue[Result | Exception], *, geographic: bool = False) -> None:
    """Deliver either a result or an error to the GUI thread."""
    try:
        if geographic:
            messages.put(solve_distance_matrix(geographic_distance_matrix(cities), config, seed=seed))
        else:
            messages.put(solve(cities, config, seed=seed))
    except Exception as error:
        messages.put(error)
