import json

import pytest

from algorithm import road_demo


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_fetch_distance_matrix_parses_valid_response(monkeypatch) -> None:
    payload = {
        "code": "Ok",
        "distances": [
            [0, 100.5],
            [140.25, 0],
        ],
    }
    requests: list[object] = []

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        requests.append(request)
        assert timeout == road_demo.REQUEST_TIMEOUT_SECONDS
        return FakeResponse(payload)

    monkeypatch.setattr(road_demo, "urlopen", fake_urlopen)
    stops = (("A", (23.5, 46.7)), ("B", (23.6, 46.8)))

    matrix = road_demo.fetch_osrm_distance_matrix(stops)

    assert matrix == [[0.0, 100.5], [140.25, 0.0]]
    assert len(requests) == 1


def test_fetch_distance_matrix_rejects_unroutable_pairs(monkeypatch) -> None:
    monkeypatch.setattr(
        road_demo,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {"code": "Ok", "distances": [[0, None], [None, 0]]}
        ),
    )

    with pytest.raises(RuntimeError, match="not routable"):
        road_demo.fetch_osrm_distance_matrix(
            (("A", (23.5, 46.7)), ("B", (23.6, 46.8)))
        )


def test_fetch_route_geometry_returns_lon_lat_points(monkeypatch) -> None:
    monkeypatch.setattr(
        road_demo,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "coordinates": [
                                [23.5, 46.7],
                                [23.55, 46.75],
                                [23.6, 46.8],
                            ]
                        }
                    }
                ],
            }
        ),
    )
    stops = (("A", (23.5, 46.7)), ("B", (23.6, 46.8)))

    points = road_demo.fetch_osrm_route_geometry(stops, [0, 1])

    assert points == [(23.5, 46.7), (23.55, 46.75), (23.6, 46.8)]


def test_fetch_tour_geometries_requests_unique_tours_once(monkeypatch) -> None:
    calls: list[tuple[int, ...]] = []

    def fake_geometry(stops, tour):
        calls.append(tuple(tour))
        return [(23.5, 46.7), (23.6, 46.8)]

    monkeypatch.setattr(road_demo, "fetch_osrm_route_geometry", fake_geometry)
    tour_history = [(0, 1), (0, 1), (1, 0)]

    geometries = road_demo.fetch_tour_geometries(
        (("A", (23.5, 46.7)), ("B", (23.6, 46.8))),
        tour_history,
    )

    assert calls == [(0, 1), (1, 0)]
    assert len(geometries) == 2


def test_fetch_route_geometry_rejects_invalid_tour() -> None:
    with pytest.raises(ValueError):
        road_demo.fetch_osrm_route_geometry(road_demo.CLUJ_STOPS, [0, 1, 2, 4])
