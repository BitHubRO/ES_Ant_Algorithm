"""Draw county boundaries, selectable seats, and geographic tours on a canvas."""

import math

from .geography import load_county_polygons, load_county_seats


class RomaniaMap:
    def __init__(self):
        self.seats = load_county_seats()
        self.polygons = load_county_polygons()
        # A local equirectangular display projection corrects longitude width.
        # Distances are calculated separately with Haversine, never from pixels.
        self.longitude_scale = math.cos(math.radians(46))
        points = [p for polygon in self.polygons for ring in polygon for p in ring]
        self.bounds = (min(p[0] for p in points), min(p[1] for p in points),
                       max(p[0] for p in points), max(p[1] for p in points))
        self.positions = {}

    def draw(self, canvas, selected_ids, tour_ids=(), *, start_id=None, route_color="#255f9a"):
        width, height = canvas.winfo_width(), canvas.winfo_height()
        self.positions = {}
        if width <= 100 or height <= 100:
            return
        lon0, lat0, lon1, lat1 = self.bounds
        dx = (lon1 - lon0) * self.longitude_scale
        dy = lat1 - lat0
        scale = min((width - 80) / dx, (height - 70) / dy)
        left, bottom = (width - dx * scale) / 2, (height - dy * scale) / 2

        def project(point):
            lon, lat = point
            return (left + (lon - lon0) * self.longitude_scale * scale,
                    height - bottom - (lat - lat0) * scale)

        for polygon in self.polygons:
            canvas.create_polygon(*[v for point in polygon[0] for v in project(point)],
                                  fill="#e0e9df", outline="#9aafa1", width=1, tags="county")
            for hole in polygon[1:]:
                canvas.create_line(*[v for point in hole for v in project(point)],
                                   fill="#9aafa1", width=1, tags="county")
        self.positions = {seat.id: project(seat.coordinates) for seat in self.seats}
        for index, city_id in enumerate(tour_ids):
            next_id = tour_ids[(index + 1) % len(tour_ids)]
            canvas.create_line(*self.positions[city_id], *self.positions[next_id],
                               fill=route_color, width=2, arrow="last", tags="route-edge")
        start = start_id if start_id is not None else tour_ids[0] if tour_ids else None
        for seat in self.seats:
            x, y = self.positions[seat.id]
            selected = seat.id in selected_ids
            color = "#d66a24" if seat.id == start else "#216fa2" if selected else "#ffffff"
            radius = 6 if selected else 5
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                               fill=color, outline="#31546d", width=1.5, tags="city-marker")
            canvas.create_text(x + 8, y - 7, text=seat.id, anchor="sw",
                               fill="#24374b", font=("Segoe UI", 9), tags="city-label")

    def hit_test(self, x, y):
        """Find only a nearby marker; blank map clicks never select a city."""
        if not self.positions:
            return None
        city_id, point = min(self.positions.items(), key=lambda item: (item[1][0] - x) ** 2 + (item[1][1] - y) ** 2)
        return city_id if math.hypot(point[0] - x, point[1] - y) <= 16 else None
