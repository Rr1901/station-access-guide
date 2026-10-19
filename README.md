# station-access-guide
This is a project to access the station of indian railways for various purpose

A FastAPI service that parses Indian Railways station data from CSV and serves lookups.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Run

```bash
.venv/bin/uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

Set `STATIONS_CSV=/path/to/file.csv` to load a different station file.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Service status and station count |
| GET | `/stations?q=&zone=&state=&limit=` | Search by code or name, filter by zone/state |
| GET | `/stations/{code}` | Station by code (case-insensitive) |
| GET | `/stations/nearby?lat=&lon=&radius_km=&limit=` | Stations within a radius, nearest first |

## Data format

`data/stations.csv` columns: `code,name,zone,state,latitude,longitude`.
The bundled file is a small sample of major stations with approximate coordinates.
The parser trims whitespace, upper-cases codes and zones, skips blank rows, and
rejects missing columns, invalid values and duplicate codes with the offending line number.

## Test

```bash
.venv/bin/python -m pytest
```
