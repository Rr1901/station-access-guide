"""FastAPI service for looking up Indian Railways stations."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.parser import Station, parse_stations
from app.store import StationStore

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "stations.csv"


class NearbyStation(BaseModel):
    station: Station
    distance_km: float


def create_app(data_path: str | Path | None = None) -> FastAPI:
    path = data_path or os.environ.get("STATIONS_CSV") or DEFAULT_DATA
    store = StationStore(parse_stations(path))

    app = FastAPI(title="Station Access Guide", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "stations": len(store)}

    @app.get("/stations", response_model=list[Station])
    def list_stations(
        q: str | None = Query(None, description="Station code or part of its name"),
        zone: str | None = Query(None, description="Railway zone code, e.g. CR"),
        state: str | None = None,
        limit: int = Query(20, ge=1, le=200),
    ):
        return store.search(q, zone=zone, state=state, limit=limit)

    # Declared before /stations/{code} so "nearby" isn't treated as a station code.
    @app.get("/stations/nearby", response_model=list[NearbyStation])
    def nearby_stations(
        lat: float = Query(ge=-90, le=90),
        lon: float = Query(ge=-180, le=180),
        radius_km: float = Query(25, gt=0, le=2000),
        limit: int = Query(10, ge=1, le=100),
    ):
        return [
            NearbyStation(station=s, distance_km=round(d, 2))
            for s, d in store.nearby(lat, lon, radius_km, limit)
        ]

    @app.get("/stations/{code}", response_model=Station)
    def get_station(code: str):
        station = store.get(code)
        if station is None:
            raise HTTPException(status_code=404, detail=f"Station {code.upper()} not found")
        return station

    return app


app = create_app()
