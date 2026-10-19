"""Parse an Indian Railways divisional accessibility PDF into a division JSON file.

Divisions publish this data in two different table layouts, and both are handled:

* list layout (e.g. Howrah, Sealdah): one row per feature, and the Remarks cell
  lists the stations that have it -
      | 8 | Availability of accessible Lift/Elevator | Howrah, Liluah, Uttarpara ... |

* station layout (e.g. Asansol): one block per station, with YES/NO and a location -
      | Name of station | Asansol |
      | 14 | Availability of accessible Lift/Elevator | YES | At PF no. 5/6 & 7 |

Usage:
    python scraper/parse_pdf.py path/to/file.pdf --division Howrah \
        --zone "Eastern Railway" --source-url https://... \
        --out data/divisions/howrah.json
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


def feature_for(item: str) -> str | None:
    item = re.sub(r"\s+", " ", item or "")
    for key, regexes in _feature_res:
        if any(rx.search(item) for rx in regexes):
            return key
    return None


def _cell(c) -> str:
    return re.sub(r"\s+", " ", (c or "")).strip()


def extract_rows(pdf_path: Path) -> list[list[str]]:
    import pdfplumber  # imported here so tests don't need it

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend([_cell(c) for c in r] for r in table)
    return rows


# ---------- station names ----------

def clean_name(token: str) -> str | None:
    token = re.sub(r"[?:*\"'()\[\]]", " ", token)
    token = re.sub(r"\s+", " ", token).strip(" .-&")
    if not token or re.search(r"\d", token):
        return None
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


def parse_list_rows(rows: list[list[str]]) -> dict:
    features: dict = {}
    for row in rows:
        if len(row) < 3:
            continue
        item, remark = row[1], row[2]
        if "any other accessibility" in item.lower():
            # free text like "Howrah-Boarding Ramp"
            if re.search(r"boarding\s+ramp", remark, re.I):
                _merge(features, "boarding_ramp",
                       {"complete": True, "stations": stations_in_remark(remark)})
            continue
        key = feature_for(item)
        if not key:
            continue
        if not remark:
            continue  # blank cell: the division gave no information
        entry: dict = {"complete": True}
        if re.fullmatch(r"nil\.?", remark, re.I):
            entry["stations"] = []
        elif ALL_STATIONS.search(remark):
            entry["all_stations"] = True
        elif (m := COUNT_ONLY.search(remark)) and not re.search(r"[A-Z][a-z]+,", remark):
            entry["complete"] = False
            entry["count_note"] = f"Official data says {m.group(1)} stations in this division have this, but doesn't name them"
        else:
            entry["stations"] = stations_in_remark(remark)
        phones = PHONE.findall(remark)
        if phones:
            entry["note"] = "Call " + " / ".join(dict.fromkeys(phones))
        if key in ("wheelchair",) and (loc := re.search(r"available at ([^.]*?)(?: in | at all|$)", remark, re.I)):
            entry.setdefault("note", f"Kept at the {loc.group(1).strip().lower()}")
        _merge(features, key, entry)
    return features


# ---------- station layout ----------

def parse_station_rows(rows: list[list[str]]) -> dict:
    features: dict = {}
    station = None
    for row in rows:
        if len(row) < 3:
            continue
        if row[0].lower().startswith("name of station"):
            station = clean_name(row[2] or row[1])
            continue
        if not station:
            continue
        key = feature_for(row[1])
        answer = row[2].strip().upper() if len(row) > 2 else ""
        if not key or answer not in ("YES", "NO"):
            continue
        location = row[3] if len(row) > 3 else ""
        entry = features.setdefault(key, {"complete": True, "per_station": {}})
        prev = entry["per_station"].get(station)
        status = "yes" if answer == "YES" else "no"
        if prev and prev["status"] == "yes":
            continue  # several rows can map to one feature; any YES wins
        item = {"status": status}
        if location and status == "yes":
            item["note"] = location
        entry["per_station"][station] = item
    return features


def detect_layout(rows: list[list[str]]) -> str:
    return "station" if any(r and r[0].lower().startswith("name of station") for r in rows) else "list"


def parse_rows(rows: list[list[str]]) -> tuple[str, dict]:
    layout = detect_layout(rows)
    return layout, (parse_station_rows(rows) if layout == "station" else parse_list_rows(rows))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--division", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    layout, features = parse_rows(extract_rows(args.pdf))
    doc = {
        "division": args.division,
        "zone": args.zone,
        "source_title": f"Accessibility data – {args.division} division ({args.zone})",
        "source_url": args.source_url,
        "retrieved": dt.date.today().isoformat(),
        "method": f"parsed-{layout}",
        "features": features,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {k: len(v.get("stations", v.get("per_station", []))) for k, v in features.items()}
    print(f"Wrote {args.out} ({layout} layout): {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
