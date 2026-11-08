"""Offline Romania data and geographic distances, independent of Tkinter."""

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

from algorithm.tsp import City, validate_distance_matrix

DATA_DIR = Path(__file__).resolve().parent / "data"
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class CountySeat:
    id: str
    name: str
    county: str
    lon: float
    lat: float

    @property
    def coordinates(self) -> City:
        """Coordinates consistently use (longitude, latitude), like GeoJSON."""
        return self.lon, self.lat


@lru_cache(maxsize=1)
def load_county_seats() -> tuple[CountySeat, ...]:
    rows = json.loads((DATA_DIR / "romania_seats.json").read_text(encoding="utf-8"))
    return tuple(CountySeat(**{key: row[key] for key in ("id", "name", "county", "lon", "lat")})
                 for row in rows)


@lru_cache(maxsize=1)
def load_county_polygons() -> tuple:
    data = json.loads((DATA_DIR / "romania_counties.geojson").read_text(encoding="utf-8"))
    polygons = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        parts = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        polygons.extend(tuple(tuple((float(p[0]), float(p[1])) for p in ring) for ring in part)
                        for part in parts)
    return tuple(polygons)


def geographic_distance_matrix(cities: tuple[City, ...]) -> list[list[float]]:
    """Haversine distances in kilometers; inputs are (longitude, latitude)."""
    if len(cities) < 2:
        raise ValueError("Select at least two cities.")
    for lon, lat in cities:
        if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Invalid geographic coordinates.")
    matrix = [[0.0] * len(cities) for _ in cities]
    for i, (lon1, lat1) in enumerate(cities):
        for j in range(i + 1, len(cities)):
            lon2, lat2 = cities[j]
            dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
            a = (math.sin(dlat / 2) ** 2
                 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
            distance = 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, a))))
            matrix[i][j] = matrix[j][i] = distance
    return validate_distance_matrix(matrix)
