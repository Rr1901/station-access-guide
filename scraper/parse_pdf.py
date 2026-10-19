"""Parse an Indian Railways divisional accessibility PDF into a division JSON file.

The PDFs are laid out "feature -> list of stations", e.g.

    13  Availability of accessible Lift/Elevator   Howrah, Liluah, Uttarpara ...

This script flips that into the division format used in data/divisions/,
which build.py then turns into one record per station.

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

# Headings that appear in the PDFs but are not features we track. Hitting one
# ends the current section so its station list doesn't leak into the previous
# feature.
STOP_PATTERNS = [
    r"ramp\s+at\s+second\s+side",
    r"ramp\s+at\s+any\s+other",
    r"braille\s+map",
    r"any\s+other\s+accessibility",
    r"^\s*[A-Z]\)\s",
    r"\bsl\.?\s*no\b",
]

NOISE_WORDS = {
    "nil", "yes", "no", "na", "n/a", "none", "only", "at", "station", "stations",
    "all", "mobile", "mob", "contact", "remarks", "item", "available",
}

_feature_res = [(f["key"], [re.compile(p, re.I) for p in f["patterns"]]) for f in FEATURES]
_stop_res = [re.compile(p, re.I) for p in STOP_PATTERNS]


def extract_text(pdf_path: Path) -> str:
    import pdfplumber  # imported here so tests don't need it

    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _match_heading(line: str):
    """Return (feature_key or None, text after the heading) if the line starts a section."""
    best = None
    for key, regexes in _feature_res:
        for rx in regexes:
            m = rx.search(line)
            if m and (best is None or m.start() < best[1].start()):
                best = (key, m)
    if best:
        return best[0], line[best[1].end():]
    for rx in _stop_res:
        if rx.search(line):
            return None, ""
    return False, None  # not a heading


def split_sections(text: str) -> dict[str, str]:
    """Group the PDF text into {feature_key: raw text that follows its heading}."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if not line.strip():
            continue
        key, rest = _match_heading(line)
        if key is False:  # ordinary line: belongs to the open section
            if current:
                sections[current].append(line)
            continue
        current = key  # a feature key, or None for a heading we skip
        if key:
            sections.setdefault(key, []).append(rest)
    return {k: "\n".join(v) for k, v in sections.items()}


def clean_name(token: str) -> str | None:
    token = re.sub(r"^\s*(\(?[0-9ivx]+[.)]|\d+)\s*", "", token, flags=re.I)  # list numbering
    token = re.sub(r"[?:*\"'()\[\]]", " ", token)
    token = re.sub(r"\s+", " ", token).strip(" .-")
    # filler around names, e.g. "Yes at Howrah only"
    token = re.sub(r"^((yes|at|in|on|available|only)\b\s*)+", "", token, flags=re.I)
    token = re.sub(r"(\s*\b(only|station|stations|jn)\b)+$", "", token, flags=re.I).strip(" .-")
    if not token or re.search(r"\d", token):
        return None  # phone numbers, platform counts, serial numbers
    if token.lower() in NOISE_WORDS or len(token) < 3 or len(token) > 40:
        return None
    if len(token.split()) > 4:
        return None  # a sentence, not a station name
    return token.title() if token.isupper() or token.islower() else token


def split_stations(raw: str) -> list[str]:
    parts = re.split(r"\b\d+\s*[.)]\s*|,|;|\n|\band\b|&|\.\s|-\s", raw)
    seen, out = set(), []
    for p in parts:
        name = clean_name(p)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def parse_text(text: str) -> dict:
    features = {}
    for key, raw in split_sections(text).items():
        entry: dict = {"complete": True}
        if re.search(r"\ball\s+(the\s+)?stations\b|\bevery\s+station\b", raw, re.I):
            entry["all_stations"] = True
        stations = split_stations(raw)
        if stations:
            entry["stations"] = stations
        phones = re.findall(r"\b[6-9]\d{9}\b", raw)
        if phones:
            entry["note"] = "Contact: " + " / ".join(dict.fromkeys(phones))
        features[key] = entry
    return features


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--division", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    features = parse_text(extract_text(args.pdf))
    doc = {
        "division": args.division,
        "zone": args.zone,
        "source_title": f"Accessibility data – {args.division} division ({args.zone})",
        "source_url": args.source_url,
        "retrieved": dt.date.today().isoformat(),
        "method": "parsed",
        "method_note": "Generated by scraper/parse_pdf.py. Review the station names before committing.",
        "features": features,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {k: len(v.get("stations", [])) for k, v in features.items()}
    print(f"Wrote {args.out}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
