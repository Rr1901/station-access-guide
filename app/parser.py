"""Parse Indian Railways station data from CSV into validated Station records."""

import csv
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

REQUIRED_COLUMNS = ("code", "name", "zone", "state", "latitude", "longitude")


class Station(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    name: str = Field(min_length=1)
    zone: str
    state: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator("code", "zone")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", "state")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class StationParseError(ValueError):
    """Raised when the station file is malformed; message includes the line number."""


def parse_stations(path: str | Path) -> list[Station]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise StationParseError(f"{path}: missing columns: {', '.join(missing)}")

        stations: list[Station] = []
        seen: set[str] = set()
        for row in reader:
            line = reader.line_num
            if not any((v or "").strip() for v in row.values()):
                continue
            try:
                station = Station(**{c: row[c] for c in REQUIRED_COLUMNS})
            except ValidationError as exc:
                fields = ", ".join(str(e["loc"][0]) for e in exc.errors())
                raise StationParseError(f"{path}:{line}: invalid {fields}") from exc
            if station.code in seen:
                raise StationParseError(f"{path}:{line}: duplicate code {station.code}")
            seen.add(station.code)
            stations.append(station)
    return stations
