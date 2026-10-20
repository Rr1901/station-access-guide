"""Parse an Indian Railways divisional accessibility PDF into a division JSON file.

Divisions publish this data in two different table layouts, and both are handled:

* list layout (e.g. Howrah, Sealdah): one row per feature, and the Remarks cell
  lists the stations that have it -
      | 8 | Availability of accessible Lift/Elevator | Howrah, Liluah, Uttarpara ... |

  Some divisions (e.g. Malda) add a Yes/No column and name stations by code -
      | 8 | Availability of accessible Lift/Elevator? | Yes | MLDT, BGP, JMP ... |

* station layout (e.g. Asansol, West Central Railway): one block per station, with
  YES/NO and a location; the Availability column is found from the header row -
      | Name of station | Asansol |
      | 14 | Availability of accessible Lift/Elevator | YES | At PF no. 5/6 & 7 |

* grid layout (e.g. Pune): one row per station, one column per feature -
      | SN | Station | STN Code | Category | No of Wheel chairs | ... | Lifts | ...
      | 2  | Kolhapur | KOP     | NSG-3    | Available          | ... | Not applicable |

Usage:
    python scraper/parse_pdf.py path/to/file.pdf --division Howrah \
        --zone "Eastern Railway" --source-url https://... \
        --out data/divisions/howrah.json [--pages 1-8,30-31] [--codes stations.json]

--pages applies to every PDF given; a .json transcription is always read whole.

The input can also be a .json list of table rows, for scanned pages transcribed
by hand (see data/transcribed/). --codes takes the datameet station list
(https://github.com/datameet/railways, CC0) to turn station codes into names.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import FEATURES  # noqa: E402

_feature_res = [(f["key"], [re.compile(p, re.I) for p in f["patterns"]]) for f in FEATURES]

NOISE = {"nil", "yes", "no", "na", "n/a", "none", "available", "mobile", "station", "stations"}
PHONE = re.compile(r"\b[6-9]\d{9}\b")
# "at 150 stations", "in 148 nos of stations": a count with no names
COUNT_ONLY = re.compile(r"\b(\d+)\s*(nos\.?\s*(of\s*)?)?stations?\b", re.I)
ALL_STATIONS = re.compile(r"\ball\s+sta\w*ions?\b", re.I)  # also catches the typo "staions"
CODE_LIST = re.compile(r"[A-Z]{2,5}(\s*,\s*[A-Z\s]{2,7})*[\s.]*")  # "BGP", "AKN, BDAG, JM\nQ, ..."
# "Not applicable" means the rules don't require it at this station category; it doesn't say whether
# the station has it (Mumbai's list marks lifts "not applicable" at Kurla, which has them).
NA_NOTE = "Not required at a station of this size, so the official list doesn't say"
# Unfilled template text in the location column of the West Central Railway forms
PLACEHOLDER = re.compile(r"^(na|location\s*\(s\)|at platform no/s\W*|no\. of parking.*|location to be .*|"
                         r"location of help booth to be indicated|specify the features.*|"
                         r"secondary side entry available/not available|phon no\..*|not applicable)$", re.I)


def feature_for(item: str) -> str | None:
    item = re.sub(r"\s+", " ", item or "")
    for key, regexes in _feature_res:
        if any(rx.search(item) for rx in regexes):
            return key
    return None


def _cell(c) -> str:
    return re.sub(r"\s+", " ", (c or "")).strip()


def parse_pages(spec: str | None) -> set[int] | None:
    """"1-8,30-31" -> {1, ..., 8, 30, 31}"""
    if not spec:
        return None
    pages = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        pages.update(range(int(a), int(b or a) + 1))
    return pages


def extract_rows(pdf_path: Path, pages: set[int] | None = None) -> list[list[str]]:
    if pdf_path.suffix == ".json":  # hand-transcribed scanned pages
        return [[_cell(c) for c in r] for r in json.loads(pdf_path.read_text(encoding="utf-8"))["rows"]]

    import pdfplumber  # imported here so tests don't need it

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            if pages and n not in pages:
                continue
            page_rows = [[_cell(c) for c in r] for t in page.extract_tables() for r in t]
            if not any(r and r[0].lower().startswith("name of station") for r in page_rows):
                # some forms print the station heading above the table, as plain text
                for line in (page.extract_text() or "").splitlines():
                    if m := re.match(r"\s*(Division|Name of Station)\s*:?\s*(\S.*)", line, re.I):
                        rows.append([m.group(1), m.group(2)])
            rows.extend(page_rows)
    return rows


def load_codes(path: Path | None) -> dict[str, str]:
    """datameet stations.json -> {"MLDT": "Malda Town", ...}"""
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["properties"]["code"]: " ".join(w.capitalize() for w in f["properties"]["name"].split())
            for f in data["features"] if f["properties"].get("code") and f["properties"].get("name")}


def answer(cell: str) -> str | None:
    """YES / No / "N o" / NOT APPLICABLE / AVAILABLE -> "yes" | "no" | "na" """
    t = re.sub(r"[\s.]+", " ", cell or "").strip().lower()
    if t in ("yes", "available", "avl"):
        return "yes"
    if t in ("no", "n o", "not available"):
        return "no"
    if t in ("na", "n a", "not applicable", "not application"):
        return "na"
    return None


# ---------- station names ----------

def clean_name(token: str) -> str | None:
    token = re.sub(r"[?:*\"'()\[\]]", " ", token)
    token = re.sub(r"\s+", " ", token).strip(" .-&")
    if not token or re.search(r"\d", token):
        return None
    if token.isupper() and len(token) > 5:  # "RAGHOGARH" -> "Raghogarh"; short tokens may be codes
        token = token.lower()
    if token.lower() in NOISE or len(token) < 3 or len(token) > 40 or len(token.split()) > 4:
        return None
    # "Mertala phaleya" -> "Mertala Phaleya", "Azimganj jn" -> "Azimganj Jn"
    return " ".join(w[:1].upper() + w[1:] for w in token.split())


def split_stations(raw: str) -> list[str]:
    seen, out = set(), []
    for part in re.split(r",|;|&|\band\b", raw):
        name = clean_name(part)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def stations_in_remark(remark: str) -> list[str]:
    """Remarks are either a plain list ("Howrah, Bally & Bandel") or a sentence
    ("Available at Howrah. Mobile no.- ...", "In Sealdah, wheelchair can be booked")."""
    text = PHONE.sub(" ", remark)
    if re.search(r"\b(available|booked|mobile)\b", text, re.I):
        found = re.findall(r"\b(?:[Ii]n|[Aa]t)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})", text)
        # drop words that follow a name in these sentences: "at Sealdah Mobile no-"
        found = [re.sub(r"(\s+(Mobile|Wheel\w*|No|Station))+$", "", f) for f in found]
        return split_stations(", ".join(found))
    # "Howrah-Boarding Ramp": the station is the part before the dash
    text = re.sub(r"-\s*[A-Za-z ]+$", "", text) if re.search(r"-\s*[A-Za-z]", text) else text
    return split_stations(text)


# ---------- list layout ----------

def _merge(features: dict, key: str, entry: dict) -> None:
    cur = features.setdefault(key, {"complete": True})
    cur["complete"] = cur["complete"] and entry["complete"]
    if "stations" in entry:
        cur["stations"] = list(dict.fromkeys(cur.get("stations", []) + entry["stations"]))
    for field in ("note", "count_note"):
        if entry.get(field):
            if not cur.get(field):
                cur[field] = entry[field]
            elif entry[field] not in cur[field]:
                cur[field] = f"{cur[field]} · {entry[field]}"
    if entry.get("all_stations"):
        cur["all_stations"] = True


def stations_from_codes(remark: str, codes: dict, found: dict) -> list[str]:
    out = []
    for code in re.sub(r"\s+", "", remark).strip(".").split(","):
        code = code.strip(".")
        if code:
            name = codes.get(code, code)
            found[name] = code
            out.append(name)
    return list(dict.fromkeys(out))


def parse_list_rows(rows: list[list[str]], codes: dict | None = None, found: dict | None = None) -> dict:
    codes = codes or {}
    found = found if found is not None else {}
    features: dict = {}
    for row in rows:
        if len(row) < 3:
            continue
        item, remark = row[1], row[2]
        said = None
        if len(row) > 3 and (said := answer(row[2])) or len(row) > 3 and not row[2]:
            remark = row[3]  # | 8 | Item | Yes | MLDT, BGP ... |
        if "any other accessibility" in item.lower():
            # free text like "Howrah-Boarding Ramp"
            if re.search(r"boarding\s+ramp", remark, re.I):
                _merge(features, "boarding_ramp",
                       {"complete": True, "stations": stations_in_remark(remark)})
            continue
        key = feature_for(item)
        if not key:
            continue
        if not remark and said != "no":
            continue  # blank cell: the division gave no information
        entry: dict = {"complete": True}
        if re.fullmatch(r"nil\.?", remark, re.I) or said == "no" and not CODE_LIST.fullmatch(remark):
            entry["stations"] = []
        elif CODE_LIST.fullmatch(remark):
            entry["stations"] = stations_from_codes(remark, codes, found)
        elif ALL_STATIONS.search(remark):
            entry["all_stations"] = True
        elif (m := COUNT_ONLY.search(remark)) and not re.search(r"[A-Z][a-z]+,", remark):
            entry["complete"] = False
            entry["count_note"] = f"Official data says {m.group(1)} stations in this division have this, but doesn't name them"
        else:
            entry["stations"] = stations_in_remark(remark)
            if said == "yes" and not entry["stations"]:
                # "Yes - With the help of licensee porters at Main stations": no names given
                entry = {"complete": False, "count_note": f"Official data says yes, without naming stations: “{remark.rstrip('.')}”"}
        phones = PHONE.findall(remark)
        if phones:
            entry["note"] = "Call " + " / ".join(dict.fromkeys(phones))
        if key in ("wheelchair",) and (loc := re.search(r"available at ([^.]*?)(?: in | at all|$)", remark, re.I)):
            entry.setdefault("note", f"Kept at the {loc.group(1).strip().lower()}")
        _merge(features, key, entry)
    return features


# ---------- station layout ----------

def station_heading(value: str, found: dict) -> str | None:
    """"Bayana (BXN)" -> "Bayana" (recording the code); "RAGHOGARH HALT STATION" -> "Raghogarh" """
    value = re.sub(r"^\s*:\s*", "", value)
    code = None
    if m := re.search(r"\(([A-Z]{2,5})\)", value):
        code = m.group(1)
        value = value[:m.start()]
    value = re.sub(r"\s+halt(\s+station)?\s*$", "", value.strip(), flags=re.I)
    name = clean_name(value)
    if name and code:
        found[name] = code
    return name


def station_item(said: str, location: str, remark: str) -> dict:
    notes = [t for t in (location, remark) if t and not PLACEHOLDER.match(t.strip(" .")) and answer(t) is None]
    text = " · ".join(notes)
    # "YES" for a ramp at a second entry that doesn't exist, or an FOB at a one-platform station
    if said == "yes" and re.search(r"no second entry|second (side ?)?entry not available|only one platform", text, re.I):
        said = "no"
    if said == "na":
        return {"status": "unknown", "note": NA_NOTE}
    item = {"status": said}
    if text and said == "yes":  # a location next to a NO is a form-filling slip, not information
        item["note"] = text[:1].upper() + text[1:].lower() if text.isupper() else text
    return item


def parse_station_rows(rows: list[list[str]], found: dict | None = None) -> dict:
    found = found if found is not None else {}
    features: dict = {}
    station = None
    col = 2  # Availability column; Asansol's forms have it third, WCR's vary
    for row in rows:
        if len(row) < 2:
            continue
        if row[0].lower().startswith("name of station"):
            value = next((c for c in row[1:] if c), "") or row[0][len("name of station"):]
            station = station_heading(value, found)
            continue
        hdr = [i for i, c in enumerate(row) if re.fullmatch(r"availability(\s+yes/no)?", c, re.I)]
        if hdr:
            col = hdr[0]
            continue
        if not station or len(row) <= col:
            continue
        key = feature_for(row[1])
        said = answer(row[col])
        if not key or not said:
            continue
        item = station_item(said, *(row[col + 1:col + 3] + ["", ""])[:2])
        entry = features.setdefault(key, {"complete": True, "per_station": {}})
        prev = entry["per_station"].get(station)
        if prev and prev["status"] == "yes":
            continue  # several rows can map to one feature; any YES wins
        entry["per_station"][station] = item
    return features


# ---------- grid layout ----------

UNITS = {"lift": "lift", "escalator": "escalator", "wheelchair": "wheelchair", "accessible_toilet": "toilet",
         "water_booth": "water stand", "low_counter": "counter", "battery_car": "battery car"}


def grid_item(cell: str, key: str = "") -> dict | None:
    t = re.sub(r"\s+", " ", cell).strip().lower()
    if re.search(r"being provided|will be provided|under progress|under construction", t):
        return {"status": "no", "note": "Being provided under the Amrit Bharat Station Scheme"
                if "abss" in t else "Work in progress"}
    said = answer(cell)
    if said == "na":
        return {"status": "unknown", "note": NA_NOTE}
    if said:
        return {"status": said}
    if t.isdigit():
        n = int(t)
        unit = UNITS.get(key)
        return {"status": "yes", "note": f"{n} {unit}{'s' if n > 1 else ''}"} if n and unit else {"status": "yes" if n else "no"}
    if t == "not required":
        return {"status": "unknown", "note": "The official list says it isn't needed at this station"}
    if t == "technically not feasible":
        return {"status": "no", "note": "Technically not feasible here, according to the official list"}
    if t == "no vehicular movement":
        return {"status": "no", "note": "No vehicles can reach this station"}
    if re.match(r"not (available )?on all pfs?$", t):
        return {"status": "yes", "note": "Not on all platforms"}
    if t.startswith("partial"):
        return {"status": "yes", "note": "Partly available"}
    if t.startswith("available on"):
        return {"status": "yes", "note": cell.strip()}
    if t == "ground level entry":
        return {"status": "yes", "note": "Ground-level entry, no ramp needed"}
    if t.startswith(("station manager", "dy. ss")):
        return {"status": "yes", "note": f"Ask the {cell.strip()}"}
    if PHONE.search(t):
        return {"status": "yes", "note": cell.strip()}
    if t == "no railway staff posted":
        return {"status": "no", "note": "No railway staff posted at this station"}
    return None


def parse_grid_rows(rows: list[list[str]], found: dict | None = None) -> dict:
    found = found if found is not None else {}
    features: dict = {}
    columns: dict[int, str] = {}
    for row in rows:
        if len(row) > 3 and row[1].lower() == "station":
            columns = {i: k for i, c in enumerate(row) if i > 3 and (k := feature_for(c))}
            continue
        if not columns or not row[0].isdigit():
            continue
        station = clean_name(row[1].title() if row[1].isupper() else row[1])  # "NIRA"
        if not station or any(re.search(r"not open for passenger", c, re.I) for c in row):
            continue  # e.g. Mukutban (Nagpur): listed, but no passenger trains stop
        if not station:
            continue
        if re.fullmatch(r"[A-Z]{2,5}", row[2]):
            found[station] = row[2]
        for i, key in columns.items():
            if i < len(row) and (item := grid_item(row[i], key)):
                features.setdefault(key, {"complete": True, "per_station": {}})["per_station"][station] = item
    return features


def detect_layout(rows: list[list[str]]) -> str:
    if any(len(r) > 3 and r[1].lower() == "station" and "code" in r[2].lower() for r in rows):
        return "grid"
    return "station" if any(r and r[0].lower().startswith("name of station") for r in rows) else "list"


def parse_rows(rows: list[list[str]], codes: dict | None = None, found: dict | None = None) -> tuple[str, dict]:
    layout = detect_layout(rows)
    if layout == "grid":
        return layout, parse_grid_rows(rows, found)
    if layout == "station":
        return layout, parse_station_rows(rows, found)
    return layout, parse_list_rows(rows, codes, found)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf", type=Path, nargs="+", help="one or more PDFs / transcribed .json files")
    ap.add_argument("--division", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pages", help="only these pages, e.g. 1-8,30-31")
    ap.add_argument("--source-title", help="defaults to 'Accessibility data – <division> division (<zone>)'")
    ap.add_argument("--codes", type=Path, help="datameet stations.json, to resolve station codes")
    args = ap.parse_args(argv)

    found: dict = {}
    codes = load_codes(args.codes)
    rows = [r for path in args.pdf for r in extract_rows(path, parse_pages(args.pages))]
    layout, features = parse_rows(rows, codes, found)
    doc = {
        "division": args.division,
        "zone": args.zone,
        "source_title": args.source_title or f"Accessibility data – {args.division} division ({args.zone})",
        "source_url": args.source_url,
        "retrieved": dt.date.today().isoformat(),
        "method": f"parsed-{layout}",
        "features": features,
    }
    if found:
        doc["station_codes"] = dict(sorted(found.items()))
        unresolved = sorted(c for n, c in found.items() if n == c)
        if unresolved:
            print(f"Codes with no name in --codes (kept as codes): {', '.join(unresolved)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {k: len(v.get("stations", v.get("per_station", []))) for k, v in features.items()}
    print(f"Wrote {args.out} ({layout} layout): {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
