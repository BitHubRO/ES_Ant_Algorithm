"""Small live road-routing example using the public OSRM demo server."""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen

from .tsp import City, validate_distance_matrix

OSRM_BASE_URL = "https://router.project-osrm.org"
REQUEST_TIMEOUT_SECONDS = 20

CLUJ_STOPS: tuple[tuple[str, City], ...] = (
    ("St. Michael's Church", (23.5895, 46.7699)),
    ("Central Park", (23.5775, 46.7712)),
    ("Cluj Arena", (23.5684, 46.7683)),
    ("Botanical Garden", (23.5890, 46.7556)),
)


def _fetch_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={"User-Agent": "ES-Ant-Algorithm-student-demo/1.0"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Road-routing request failed: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Road-routing service returned invalid JSON") from error

    if not isinstance(payload, dict):
        raise RuntimeError("Road-routing service returned an unexpected response")
    if payload.get("code") != "Ok":
        message = payload.get("message", "unknown routing error")
        raise RuntimeError(f"Road-routing service error: {message}")
    return payload


def fetch_osrm_distance_matrix(
    stops: Sequence[tuple[str, City]],
) -> list[list[float]]:
    """Fetch driving distances in meters for all ordered stop pairs."""
    if len(stops) < 2:
        raise ValueError("at least two stops are required")

    coordinates = ";".join(f"{lon:.6f},{lat:.6f}" for _, (lon, lat) in stops)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coordinates}?annotations=distance"
    payload = _fetch_json(url)
    matrix = payload.get("distances")
    if not isinstance(matrix, list):
        raise RuntimeError("Road-routing response did not contain a distance matrix")
    if any(not isinstance(row, list) for row in matrix):
        raise RuntimeError("Road-routing service returned a malformed distance matrix")
    if any(value is None for row in matrix for value in row):
        raise RuntimeError("At least one stop pair is not routable")

    try:
        return validate_distance_matrix(matrix)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"Road-routing service returned invalid distances: {error}") from error


def fetch_osrm_route_geometry(
    stops: Sequence[tuple[str, City]],
    tour: Sequence[int],
) -> list[City]:
    """Fetch a closed, ordered driving route as longitude/latitude points."""
    stop_count = len(stops)
    if stop_count < 2:
        raise ValueError("at least two stops are required")
    if (
        len(tour) != stop_count
        or any(not isinstance(index, int) or isinstance(index, bool) for index in tour)
        or set(tour) != set(range(stop_count))
    ):
        raise ValueError("tour must contain each stop index exactly once")

    ordered_indices = [*tour, tour[0]]
    coordinates = ";".join(
        f"{stops[index][1][0]:.6f},{stops[index][1][1]:.6f}"
        for index in ordered_indices
    )
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/{coordinates}"
        "?overview=full&geometries=geojson&steps=false"
    )
    payload = _fetch_json(url)
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise RuntimeError("Road-routing response did not contain a route")

    geometry = routes[0].get("geometry")
    if not isinstance(geometry, dict):
        raise RuntimeError("Road-routing response did not contain route geometry")
    raw_coordinates = geometry.get("coordinates")
    if not isinstance(raw_coordinates, list) or len(raw_coordinates) < 2:
        raise RuntimeError("Road-routing service returned empty route geometry")

    points: list[City] = []
    try:
        for point in raw_coordinates:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("each geometry point must contain longitude and latitude")
            lon, lat = float(point[0]), float(point[1])
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("geometry coordinates are out of geographic bounds")
            points.append((lon, lat))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"Road-routing service returned invalid geometry: {error}") from error
    return points


def fetch_tour_geometries(
    stops: Sequence[tuple[str, City]],
    tour_history: Sequence[Sequence[int]],
) -> dict[tuple[int, ...], list[City]]:
    """Fetch route geometry once for each unique tour in the iteration history."""
    geometries: dict[tuple[int, ...], list[City]] = {}
    for tour in tour_history:
        key = tuple(tour)
        if key not in geometries:
            geometries[key] = fetch_osrm_route_geometry(stops, key)
    return geometries


def osrm_attribution() -> str:
    """Return attribution for the routing data used by the demo."""
    return "Routing: OSRM demo server | Map data: © OpenStreetMap contributors"
