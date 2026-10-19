import pytest

from app.parser import StationParseError, parse_stations
from app.main import DEFAULT_DATA

HEADER = "code,name,zone,state,latitude,longitude\n"


def write(tmp_path, body, header=HEADER):
    path = tmp_path / "stations.csv"
    path.write_text(header + body, encoding="utf-8")
    return path


def test_parses_bundled_data():
    stations = parse_stations(DEFAULT_DATA)
    codes = {s.code for s in stations}
    assert {"NDLS", "CSMT", "HWH"} <= codes


def test_normalizes_fields(tmp_path):
    path = write(tmp_path, " ndls , New Delhi ,nr, Delhi ,28.64,77.21\n")
    [station] = parse_stations(path)
    assert station.code == "NDLS"
    assert station.zone == "NR"
    assert station.name == "New Delhi"
    assert station.state == "Delhi"


def test_skips_blank_rows(tmp_path):
    path = write(tmp_path, "NDLS,New Delhi,NR,Delhi,28.64,77.21\n,,,,,\n")
    assert len(parse_stations(path)) == 1


def test_missing_column(tmp_path):
    path = write(tmp_path, "NDLS,New Delhi,NR,Delhi,28.64\n", header="code,name,zone,state,latitude\n")
    with pytest.raises(StationParseError, match="missing columns: longitude"):
        parse_stations(path)


def test_invalid_coordinate_reports_line(tmp_path):
    path = write(tmp_path, "NDLS,New Delhi,NR,Delhi,28.64,77.21\nXX,Bad,NR,Delhi,abc,77\n")
    with pytest.raises(StationParseError, match=r":3: invalid latitude"):
        parse_stations(path)


def test_duplicate_code(tmp_path):
    path = write(tmp_path, "NDLS,New Delhi,NR,Delhi,28.64,77.21\nndls,Again,NR,Delhi,28.64,77.21\n")
    with pytest.raises(StationParseError, match="duplicate code NDLS"):
        parse_stations(path)
