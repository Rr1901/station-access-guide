"""In-memory lookups over parsed stations."""

import math

from app.parser import Station

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class StationStore:
    def __init__(self, stations: list[Station]):
        self._by_code = {s.code: s for s in stations}

    def __len__(self) -> int:
        return len(self._by_code)

    def get(self, code: str) -> Station | None:
        return self._by_code.get(code.strip().upper())

    def search(
        self,
        query: str | None = None,
        zone: str | None = None,
        state: str | None = None,
        limit: int = 20,
    ) -> list[Station]:
        q = (query or "").strip().lower()
        results = []
        for station in self._by_code.values():
            if zone and station.zone != zone.strip().upper():
                continue
            if state and station.state.lower() != state.strip().lower():
                continue
            if q and q not in station.name.lower() and q != station.code.lower():
                continue
            results.append(station)
        # Exact code match first, then names starting with the query, then alphabetical.
        results.sort(key=lambda s: (s.code.lower() != q, not s.name.lower().startswith(q), s.name))
        return results[:limit]

    def nearby(
        self, latitude: float, longitude: float, radius_km: float, limit: int = 10
    ) -> list[tuple[Station, float]]:
        hits = [
            (s, distance_km(latitude, longitude, s.latitude, s.longitude))
            for s in self._by_code.values()
        ]
        hits = [(s, d) for s, d in hits if d <= radius_km]
        hits.sort(key=lambda h: h[1])
        return hits[:limit]
