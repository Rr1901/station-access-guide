import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

from build import build, build_division, load_names  # noqa: E402
from parse_pdf import parse_rows, split_stations, stations_in_remark  # noqa: E402

# Rows as pdfplumber's extract_tables() returns them for the two real layouts.
LIST_ROWS = [
    ["Sl. No.", "Item", "Remarks"],
    ["1", "Is Wheelchair available?", "Wheel chair is available at Help Booth/Enquiry booth in all staions."],
    ["2", "Can Wheelchair be booked online?", "In Howrah, Wheelchair be booked online. Mobile no.-9147071681"],
    ["3", "Battery Operated Car?", "Available at Sealdah Mobile no- 9432744063"],
    ["4", "Human Assistance", ""],
    ["1", "Divyangjan Friendly Toilets", "At 150 stations"],
    ["4", "Ramp at Main Entry", "Howrah, Gnandas Kendra, Malihati Tailbpur Road & Uttarpara."],
    ["8", "Availability of accessible Lift/Elevator", "Sealdah, Kolkata, Ballyghat, Shyamnagar& Cossimbazar"],
    ["10", "Availability of Audio/Visual Braille map", "NIL"],
    ["12", "Any other accessibility features", "Howrah-Boarding Ramp"],
]

STATION_ROWS = [
    ["Division", "", "Asansol", ""],
    ["Name of station", "", "Madhupur", ""],
    ["Sl. No.", "Name of facility", "Availability", "Availability with location"],
    ["1", "Is wheel chair available", "YES", "At Enquiry office"],
    ["2", "Battery Operated car", "NO", ""],
    ["3", "Human Assistance", "NO", ""],
    ["4", "Booking of human assistance", "YES", "On request"],
    ["14", "Availability of accessible Lift/Elevator", "YES", "At PF no. 2/3 & 4/5"],
]


def test_split_stations():
    assert split_stations("Howrah, Bally & Bandel.") == ["Howrah", "Bally", "Bandel"]
    assert split_stations("Mertala phaleya, Azimganj jn") == ["Mertala Phaleya", "Azimganj Jn"]


def test_stations_in_sentences():
    assert stations_in_remark("Available at Sealdah Mobile no- 9432744063") == ["Sealdah"]
    assert stations_in_remark("In Howrah, Wheelchair be booked online.") == ["Howrah"]
    assert stations_in_remark("Howrah-Boarding Ramp") == ["Howrah"]


def test_list_layout():
    layout, f = parse_rows(LIST_ROWS)
    assert layout == "list"
    assert f["wheelchair"]["all_stations"] is True            # "staions" typo still matched
    assert f["wheelchair_booking"]["stations"] == ["Howrah"]
    assert f["wheelchair_booking"]["note"] == "Call 9147071681"
    assert f["battery_car"]["stations"] == ["Sealdah"]
    assert "human_assistance" not in f                       # blank cell = no information
    assert f["accessible_toilet"]["complete"] is False       # count only, no names
    assert "150" in f["accessible_toilet"]["count_note"]
    assert f["lift"]["stations"] == ["Sealdah", "Kolkata", "Ballyghat", "Shyamnagar", "Cossimbazar"]
    assert f["braille_map"] == {"complete": True, "stations": []}  # NIL = none
    assert f["boarding_ramp"]["stations"] == ["Howrah"]


def test_station_layout():
    layout, f = parse_rows(STATION_ROWS)
    assert layout == "station"
    assert f["lift"]["per_station"]["Madhupur"] == {"status": "yes", "note": "At PF no. 2/3 & 4/5"}
    assert f["battery_car"]["per_station"]["Madhupur"]["status"] == "no"
    assert f["human_assistance"]["per_station"]["Madhupur"]["status"] == "yes"  # any YES wins


def test_statuses_and_aliases():
    _, lookup = load_names()
    div = {"features": {
        "lift": {"complete": True, "stations": ["Howrah"]},
        "ramp_entry": {"complete": True, "stations": ["Gnandas Kendra", "Burdwan"]},
        "accessible_toilet": {"complete": False, "count_note": "150 stations"},
    }}
    st = build_division(div, lookup)
    assert "Jnandas Kendra" in st and "Gnandas Kendra" not in st      # typo alias
    assert st["Barddhaman"]["lift"]["status"] == "not_listed"         # complete list, absent
    assert st["Howrah"]["accessible_toilet"] == {"status": "unknown", "note": "150 stations"}
    assert st["Howrah"]["parking"]["status"] == "unknown"             # feature not published


def test_real_build():
    data = build()
    names = [s["name"] for s in data["stations"]]
    assert len(names) == len(set(names))
    by = {s["name"]: s for s in data["stations"]}
    assert by["Howrah"]["code"] == "HWH" and by["Howrah"]["features"]["lift"]["status"] == "yes"
    assert by["Asansol"]["features"]["battery_car"]["status"] == "no"
    assert by["Sealdah"]["features"]["battery_car"]["status"] == "yes"
    assert json.dumps(data)
