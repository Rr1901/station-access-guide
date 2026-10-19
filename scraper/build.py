"""Combine data/divisions/*.json into site/data/stations.json (one record per station).

    python scraper/build.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import FEATURES, FEATURE_KEYS, NOT_LISTED, UNKNOWN, YES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIVISIONS_DIR = ROOT / "data" / "divisions"
NAMES_FILE = ROOT / "data" / "station_names.json"
OUT_FILE = ROOT / "site" / "data" / "stations.json"


def _key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def load_names(path: Path = NAMES_FILE) -> tuple[dict, dict]:
    """Return (canonical -> info, lookup key -> canonical) including aliases."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    canon = {k: v for k, v in raw.items() if not k.startswith("_")}
    lookup = {}
    for name, info in canon.items():
        lookup[_key(name)] = name
        for alias in info.get("aliases", []):
            lookup[_key(alias)] = name
    return canon, lookup


def canonical(name: str, lookup: dict) -> str:
    return lookup.get(_key(name), name.strip())


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_division(div: dict, lookup: dict) -> dict[str, dict]:
    """Return {canonical station name: {feature_key: {status, note?}}} for one division."""
    feats = div.get("features", {})
    listed = {
        key: {canonical(s, lookup) for s in entry.get("stations", [])}
        for key, entry in feats.items()
    }
    all_names = set().union(*listed.values()) if listed else set()

    stations = {}
    for name in sorted(all_names):
        record = {}
        for key in FEATURE_KEYS:
            entry = feats.get(key)
            if entry is None:
                record[key] = {"status": UNKNOWN}
                continue
            if entry.get("all_stations") or name in listed[key]:
                item = {"status": YES}
                if entry.get("note"):
                    item["note"] = entry["note"]
            elif entry.get("complete"):
                item = {"status": NOT_LISTED}
            else:
                item = {"status": UNKNOWN}
            record[key] = item
        stations[name] = record
    return stations


def build(divisions_dir: Path = DIVISIONS_DIR, names_file: Path = NAMES_FILE) -> dict:
    canon, lookup = load_names(names_file)
    out_divisions, out_stations = [], []
    for path in sorted(divisions_dir.glob("*.json")):
        div = json.loads(path.read_text(encoding="utf-8"))
        out_divisions.append({k: div.get(k) for k in
                              ("division", "zone", "source_title", "source_url",
                               "retrieved", "method", "method_note")})
        for name, features in build_division(div, lookup).items():
            info = canon.get(name, {})
            out_stations.append({
                "id": slug(name),
                "name": name,
                "code": info.get("code", ""),
                "aliases": info.get("aliases", []),
                "division": div["division"],
                "zone": div["zone"],
                "features": features,
            })
    out_stations.sort(key=lambda s: s["name"])
    return {
        "generated": dt.date.today().isoformat(),
        "features": [{"key": f["key"], "label": f["label"]} for f in FEATURES],
        "divisions": out_divisions,
        "stations": out_stations,
    }


def main() -> int:
    data = build()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE.relative_to(ROOT)}: {len(data['stations'])} stations "
          f"from {len(data['divisions'])} division(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
