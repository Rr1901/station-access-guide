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

Every feature at every station gets one of three states:

| State | Meaning |
|---|---|
| ✓ Available | The station is named in the official list for that feature |
| – Not listed | We have the **complete** official list and the station isn't in it |
| ? No data yet | We only have part of the list, so we can't say |

"Not listed" and "No data yet" are deliberately kept apart: a missing station in a partial list must never be shown as "no lift".

## Data coverage

| Division | Zone | Stations | Status |
|---|---|---|---|
| Howrah | Eastern Railway | 23 | Lifts, help booths, FOB ramps, battery car, wheelchair booking and Braille signage complete; toilets, water booths, entry ramps and parking partial (entered by hand) |

Next: parse the full Howrah PDF (about 190 stations), then Sealdah and Asansol, then the zone-wise lists published by the Railway Board.

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

Review the generated station names before committing; PDFs differ in layout. Add new codes and alternate spellings to `data/station_names.json`.

## Deploying

Pushing to `main` runs the tests, rebuilds the data and publishes `site/` to GitHub Pages. One-time setup: **Settings → Pages → Source: GitHub Actions**.

## Corrections

Every station page has a "Something wrong or missing?" link that opens a GitHub issue for that station.

## Disclaimer

Not an official Indian Railways service. Facilities can change, so check with the station before relying on one. Data is from Indian Railways' published accessibility documents; each station page links its source and the date it was checked.
