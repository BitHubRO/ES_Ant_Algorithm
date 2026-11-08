"""Compare three searches on one validated matrix and a matched tour budget."""

from dataclasses import dataclass
from time import perf_counter

from .aco import Config, IterationProgress, Result, _solve_with_distances
from .baselines import _nearest_neighbor_with_distances, _random_search_with_distances
from .tsp import validate_distance_matrix

METHODS = ("aco", "nearest_neighbor", "random_search")
METHOD_NAMES = {"aco": "ACO", "nearest_neighbor": "NN (all starts)", "random_search": "Random search"}
METHOD_COLORS = {"aco": "#3274a1", "nearest_neighbor": "#27834c", "random_search": "#9754b5"}


@dataclass(frozen=True)
class MethodReport:
    method: str
    result: Result
    evaluations: int
    evaluation_history: tuple[int, ...]


@dataclass(frozen=True)
class ComparisonEvent:
    method: str
    state: str
    report: MethodReport | None = None
    progress: IterationProgress | None = None


@dataclass(frozen=True)
class ComparisonFinished:
    reports: dict[str, MethodReport]


def compare_distance_matrix(cost_matrix, config=None, seed=None, *, symmetric_pheromones=False,
                            callback=None, cancel_check=None, record_pheromones=False):
    """Sequential searches; callback/animation time is excluded from timings."""
    config = config if config is not None else Config()
    distances = validate_distance_matrix(cost_matrix)
    n = len(distances)
    ants = config.ants or n
    budget = ants * config.iterations
    reports = {}

    def emit(method, state, report=None, progress=None):
        if cancel_check is not None:
            cancel_check()
        if callback is not None:
            callback(ComparisonEvent(method, state, report, progress))

    emit("nearest_neighbor", "running")
    started = perf_counter()
    tour, length = _nearest_neighbor_with_distances(distances, cancel_check)
    elapsed = perf_counter() - started
    nn = Result(tuple(tour), length, [length], [tuple(tour)], compute_seconds=elapsed)
    reports["nearest_neighbor"] = MethodReport("nearest_neighbor", nn, n, (n,))
    emit("nearest_neighbor", "finished", reports["nearest_neighbor"])

    emit("random_search", "running")
    random_result = _random_search_with_distances(
        distances, budget, seed, batch_size=ants,
        progress_callback=lambda progress: emit("random_search", "progress", progress=progress))
    evaluations = tuple(ants * (i + 1) for i in range(config.iterations))
    reports["random_search"] = MethodReport("random_search", random_result, budget, evaluations)
    emit("random_search", "finished", reports["random_search"])

    emit("aco", "running")
    aco_result = _solve_with_distances(
        distances, config, seed, symmetric_pheromones,
        progress_callback=lambda progress: emit("aco", "progress", progress=progress),
        record_pheromones=record_pheromones)
    reports["aco"] = MethodReport("aco", aco_result, budget, evaluations)
    emit("aco", "finished", reports["aco"])
    return reports
