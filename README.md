# Station Access Guide

Search an Indian railway station and see, on one page, whether it has lifts, ramps, wheelchairs, battery cars, accessible toilets and other facilities, with booking phone numbers where they exist.

**Live site:** https://rr1901.github.io/station-access-guide/ (after GitHub Pages is switched on, see below)

## Why

Indian Railways publishes accessibility data for its divisions, but only as PDFs arranged by feature ("stations with lifts: …"). Someone in a wheelchair, an elderly parent, or anyone with heavy luggage wants the opposite: *"I'm going to Barddhaman — what's there?"* This project turns those PDFs into one searchable page per station.

## How it works

```
official PDF ──► scraper/parse_pdf.py ──► data/divisions/<division>.json
                                                │
data/station_names.json (codes, spellings) ─────┤
                                                ▼
                                        scraper/build.py
                                                ▼
                                   site/data/stations.json ──► static site (GitHub Pages)
```

Every feature at every station gets one of four states:

| State | Meaning |
|---|---|
| ✓ Available | The official data says the station has it (with platform/location where given) |
| ✕ Not available | The official data explicitly says it doesn't |
| – Not listed | We have the **complete** official list and the station isn't in it |
| ? No data yet | The division hasn't published this detail by station |

"Not listed" and "No data yet" are deliberately kept apart: a station missing from an incomplete list must never be shown as "no lift".

## Data coverage

169 stations from three Eastern Railway divisions, all parsed from the official PDFs:

| Division | Stations | What the PDF gives |
|---|---|---|
| Howrah | 158 | Full station lists for every feature |
| Sealdah | 6 | Names only for lifts, help booths, Braille, parking; toilets and ramps are given only as counts ("at 150 stations"), so those show as "No data yet" |
| Asansol | 5 | Explicit YES/NO per station, with platform locations (e.g. "Lift at PF 2/3 & 4/5") |

Known PDF typos (Gnandas/Jnandas Kendra, Tailbpur/Talibpur, …) are merged through aliases in `data/station_names.json`.

Next: other zones' published lists (the Railway Board's Gati Shakti directorate has zone-wise files), and station codes for the smaller halts.

## Run it locally

```bash
pip install -r requirements.txt
python -m pytest -q tests            # parser + build tests
python scraper/build.py              # regenerate site/data/stations.json
cd site && python -m http.server     # open http://localhost:8000
```

Add a division from its PDF:

```bash
python scraper/parse_pdf.py path/to/Sealdah.pdf --division Sealdah \
  --zone "Eastern Railway" --source-url "https://…" --out data/divisions/sealdah.json
python scraper/build.py
```

Review the generated station names before committing. The parser detects both layouts the divisions use (feature lists and per-station blocks). Add new codes and alternate spellings to `data/station_names.json`.

## Deploying

Pushing to `main` runs the tests, rebuilds the data and publishes `site/` to GitHub Pages. One-time setup: **Settings → Pages → Source: GitHub Actions**.

## Corrections

Every station page has a "Something wrong or missing?" link that opens a GitHub issue for that station.

## Disclaimer

Not an official Indian Railways service. Facilities can change, so check with the station before relying on one. Data is from Indian Railways' published accessibility documents; each station page links its source and the date it was checked.
