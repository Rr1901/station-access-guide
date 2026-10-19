import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

from build import build, build_division, load_names  # noqa: E402
from parse_pdf import parse_text, split_stations  # noqa: E402

SAMPLE = """
Sl. No. Item Remarks
1 Is Wheelchair available? Yes, at all stations in Help Booth
2 Can Wheelchair be booked online? Yes, at Howrah only. Mob- 9147071681
13 Availability of accessible Lift/Elevator Howrah, Liluah, Uttarpara,
Sheoraphuli, Barddhaman
12 Ramp at Second Side Entry NIL
Divyang Friendly Toilet/s 1. HOWRAH 2. Bolpur 3. Katwa
Availability of Braille Signage Howrah
"""


def test_split_stations_drops_noise_and_numbers():
    assert split_stations("1. Howrah, 2. Liluah; NIL and Mob 9147071681") == ["Howrah", "Liluah"]


def test_parse_sections():
    f = parse_text(SAMPLE)
    assert f["wheelchair"].get("all_stations") is True
    assert f["lift"]["stations"] == ["Howrah", "Liluah", "Uttarpara", "Sheoraphuli", "Barddhaman"]
    assert f["wheelchair_booking"]["stations"] == ["Howrah"]
    assert "9147071681" in f["wheelchair_booking"]["note"]
    # "Ramp at Second Side Entry NIL" must not leak into the lift list
    assert "Nil" not in f["lift"]["stations"]
    assert f["accessible_toilet"]["stations"] == ["Howrah", "Bolpur", "Katwa"]
    assert f["braille_signage"]["stations"] == ["Howrah"]


def test_status_yes_notlisted_unknown():
    _, lookup = load_names()
    div = {"features": {
        "lift": {"complete": True, "stations": ["Howrah"]},
        "accessible_toilet": {"complete": False, "stations": ["Burdwan"]},
    }}
    st = build_division(div, lookup)
    assert st["Howrah"]["lift"]["status"] == "yes"
    assert st["Barddhaman"]["lift"]["status"] == "not_listed"        # complete list, absent
    assert st["Howrah"]["accessible_toilet"]["status"] == "unknown"  # partial list, absent
    assert st["Barddhaman"]["accessible_toilet"]["status"] == "yes"  # alias Burdwan resolved
    assert st["Howrah"]["parking"]["status"] == "unknown"            # feature not in file


def test_real_build_is_consistent():
    data = build()
    names = [s["name"] for s in data["stations"]]
    assert len(names) == len(set(names))
    howrah = next(s for s in data["stations"] if s["name"] == "Howrah")
    assert howrah["code"] == "HWH"
    assert howrah["features"]["lift"]["status"] == "yes"
    assert json.dumps(data)  # serialisable
