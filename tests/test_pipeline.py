import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

from build import build, build_division, load_names  # noqa: E402
from parse_pdf import parse_rows, split_stations, stations_in_remark  # noqa: E402

# Rows as pdfplumber's extract_tables() returns them for the real layouts.
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


# Malda: a Yes/No column, and stations named by code
CODED_ROWS = [
    ["1.", "Is Wheel chair available?", "Yes", "Wheel Chair available in 67 stations at Help Booth"],
    ["5.", "Booking of human assistance?", "Yes", "With the help of licensee porters at Main stations."],
    ["8", "Availability of accessible Lift/Elevator?", "Yes", "MLDT, BGP, JMP, JM\nQ, JMP."],
    ["9", "Availability of Help booth/Enquiry?", "No", ""],
    ["10", "Availability of Audio/Visual Braile map?", "Yes", "BGP"],
]
CODES = {"MLDT": "Malda Town", "BGP": "Bhagalpur", "JMP": "Jamalpur Jn", "JMQ": "Jamirghata"}

# West Central Railway: Availability is the 5th column, after "Applicable"
WCR_ROWS = [
    ["Division", "", "BHOPAL", "HALT STATION"],
    ["Name of station", "", "RAGHOGARH"],
    ["Sr. No.", "Name of facility", "Applicability category", "Applicable", "Availability", "Location"],
    ["1", "Is wheel chair available", "NSG 1-6", "NO", "NOT APPLICABLE", ""],
    ["4", "Dedicated parking for Divyangjan", "All stations", "YES", "YES", "IN CIRCULATING AREA"],
    ["8", "Ramp at Second Entry", "All stations", "YES", "YES", "NO SECOND ENTRY"],
    ["Name of Station", "Bayana (BXN)"],
    ["Sr. No.", "Name of Facility", "Required Category", "Availability YES/NO", "Locaton", "Remark"],
    ["7", "Ramp at Main Entry", "All stns", "AVAILABLE", "Location (s)", "Under ABSS work"],
    ["", "Can Wheetchair be booked online", "", "NO", "Accompanied by Porter", ""],
]

# Pune: one row per station
GRID_ROWS = [
    ["SN", "Station", "STN Code", "Category", "No of Wheel chairs", "Lifts", "Escalator", "Ramp in FOB/Subway"],
    ["Norms", "", "", "", "NSG1 to NSG6", "NSG1 to NSG3", "NSG1 to NSG3", "NSG 1 to 3"],
    ["1", "Pune", "Pune", "NSG-1", "Available", "work is under progress.", "Available", "Available"],
    ["34", "NIRA", "NIRA", "NSG 6", "Available", "Not applicable", "Not applicable", "being provided in ABSS"],
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


def test_coded_list_layout():
    found = {}
    layout, f = parse_rows(CODED_ROWS, CODES, found)
    assert layout == "list"
    assert f["lift"]["stations"] == ["Malda Town", "Bhagalpur", "Jamalpur Jn", "Jamirghata"]  # "JM\nQ" rejoined
    assert found["Jamirghata"] == "JMQ"
    assert f["braille_map"]["stations"] == ["Bhagalpur"]                 # single code, "Braile" typo
    assert f["help_booth"] == {"complete": True, "stations": []}         # explicit No
    assert "67" in f["wheelchair"]["count_note"]
    assert f["human_assistance"]["complete"] is False                     # yes, but no station named
    assert "Main" not in f["human_assistance"].get("stations", [])


def test_wcr_station_layout():
    found = {}
    layout, f = parse_rows(WCR_ROWS, None, found)
    assert layout == "station"
    assert f["wheelchair"]["per_station"]["Raghogarh"]["status"] == "no"
    assert "require" in f["wheelchair"]["per_station"]["Raghogarh"]["note"]
    assert f["parking"]["per_station"]["Raghogarh"] == {"status": "yes", "note": "In circulating area"}
    assert f["ramp_second"]["per_station"]["Raghogarh"]["status"] == "no"   # "YES" but no second entry
    assert f["ramp_entry"]["per_station"]["Bayana"] == {"status": "yes", "note": "Under ABSS work"}
    assert f["wheelchair_booking"]["per_station"]["Bayana"]["status"] == "no"
    assert found == {"Bayana": "BXN"}


def test_grid_layout():
    found = {}
    layout, f = parse_rows(GRID_ROWS, None, found)
    assert layout == "grid"
    assert f["lift"]["per_station"]["Pune"] == {"status": "no", "note": "Work in progress"}
    assert f["escalator"]["per_station"]["Pune"]["status"] == "yes"
    assert f["lift"]["per_station"]["Nira"]["status"] == "no"
    assert "Amrit Bharat" in f["ramp_fob"]["per_station"]["Nira"]["note"]
    assert found == {"Nira": "NIRA"}                                     # "Pune" in the code column isn't a code


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
    ids = [s["id"] for s in data["stations"]]
    assert len(ids) == len(set(ids))
    pairs = [(s["name"], s["division"]) for s in data["stations"]]
    assert len(pairs) == len(set(pairs))
    by = {s["name"]: s for s in data["stations"] if s["name"] != "Madhavnagar"}
    assert {s["code"] for s in data["stations"] if s["name"] == "Madhavnagar"} == {"MDVR", "MDRR"}
    assert by["Malda Town"]["features"]["ramp_second"]["status"] == "yes"      # "Malda." alias
    assert by["Sainagar Shirdi"]["code"] == "SNSI"
    wr = {d["division"]: d for d in data["divisions"] if d["zone"] == "Western Railway"}
    assert all(d["method"] == "secondary" and d["sources"] for d in wr.values())
    assert by["Okha"]["features"]["escalator"]["status"] == "no"
    assert by["Vadodara"]["features"]["escalator"]["note"].startswith("6 escalators")
    assert by["Valsad"]["features"]["lift"]["status"] == "no"                  # "–" in the table
    assert by["Chhayapuri"]["features"]["escalator"]["status"] == "yes"        # 2025 report over 2023 "–"
    assert "Amrit Bharat" in by["Morbi"]["notes"]                              # note-only station kept
    assert len(by["Morbi"]["sources"]) == 1 and "amrit-bharat" in by["Morbi"]["sources"][0]  # only its own source
    gj = json.loads((ROOT / "data/transcribed/gujarat_lifts_escalators_2023.json").read_text())
    n = lambda x: 0 if x == "–" else int(x)
    assert sum(n(r[4]) for r in gj["rows"]) == 54 and sum(n(r[5]) for r in gj["rows"]) == 93
    assert by["Jamnagar"]["features"]["ramp_entry"]["status"] == "unknown"   # partial source: no "not listed"
    assert by["Howrah"]["code"] == "HWH" and by["Howrah"]["features"]["lift"]["status"] == "yes"
    assert by["Asansol"]["features"]["battery_car"]["status"] == "no"
    assert by["Sealdah"]["features"]["battery_car"]["status"] == "yes"
    assert json.dumps(data)
