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

688 stations from sixteen divisions in four zones. 634 come from official railway lists:

| Division | Zone | Stations | What the PDF gives |
|---|---|---|---|
| Howrah | Eastern | 158 | Full station lists for every feature |
| Mumbai | Central | 113 | Every local station from CSMT to Kasara, Khopoli and Uran, from the division's "Divyangjan Amenities at Stns." sheet, plus Divyangjan Sahayak (Dy. SS Commercial) numbers for CSMT, Dadar, LTT, Thane, Kalyan and Panvel |
| Nagpur | Central | 93 | Grid with counts of lifts, escalators, wheelchairs, toilets (Mukutban skipped: not open to passengers). The PDF prints 0 lifts at Nagpur and 8 at Wardha, which looks like a mix-up in the source; it's shown as printed |
| Solapur | Central | 58 | Yes/No grid; the PDF is a scan, hand-transcribed in `data/transcribed/` |
| Pune | Central | 101 | Every station in a grid, including lifts, escalators, low counters, tactile paths; "Not applicable" (not required at that station size) and "being provided under ABSS" are kept as notes |
| Malda | Eastern | 69 | Full lists, but by station code; codes are turned into names with the CC0 [datameet station list](https://github.com/datameet/railways). Wheelchairs are given only as "67 stations", so they show as "No data yet" |
| Jabalpur | West Central | 12 | YES/NO per station with locations. 8 of these pages are scans; they are hand-transcribed in `data/transcribed/` |
| Bhopal | West Central | 10 | YES/NO per station (mostly halts) |
| Kota | West Central | 9 | YES/NO per station |
| Sealdah | Eastern | 6 | Names only for lifts, help booths, Braille, parking; toilets and ramps are given only as counts |
| Asansol | Eastern | 5 | Explicit YES/NO per station, with platform locations |

The West Central Railway file covers only a sample of each division's stations, not the whole division.

"Not applicable" in the official lists means the rules don't require that facility at a station of that size; it doesn't say whether the station has it (Mumbai's sheet marks lifts "not applicable" at Kurla and Ghatkopar, which have them). So it shows as "No data yet" with that explanation, never as "Not available".

**Western Railway (secondary sources).** Western Railway hasn't published station-wise accessibility lists, so 54 of its stations (all of Gujarat's larger ones, plus Mumbai Central) are built by `scraper/western_railway.py` from:

- a Lok Sabha answer listing lifts and escalators at all 39 Gujarat stations that had them on 31 July 2023, as printed by DeshGujarat (table kept in `data/transcribed/`, totals checked: 54 escalators, 93 lifts);
- DeshGujarat reports on Rajkot (2022), Chhayapuri (2025) and the 18 Amrit Bharat stations inaugurated in May 2025 (shown as a station note: the report doesn't say which station got which facility);
- IRCTC's e-wheelchair page (Ahmedabad, Mumbai Central) and an older Ahmedabad division presentation (Bhuj).

These divisions are marked `"method": "secondary"`; station pages say so at the top and list every source. A few stations were placed in a division by route rather than from a source (Khambhaliya, Kanalus, Jamwanthali, Morbi, Mithapur, Jamjodhpur, Rajula, Ekta Nagar, Karamsad, Derol, Uttran), and sources disagree on Surendranagar (Rajkot or Bhavnagar) and Gandhigram (Bhavnagar or Ahmedabad); corrections welcome.

Known gaps: three Malda codes (BPBS, NALE, UXN) aren't in the open station list, so those stations show by code until someone adds their names to `data/station_names.json`. Six Bhopal halts have no code yet. PDF typos (Gnandas/Jnandas Kendra, Sainagar Shirdih, …) are merged through aliases.

Next: other zones' station-wise PDFs (Northern, Western, Southern, South Central, …), which aren't indexed by search engines; they need to be found on each zone's website.

## Roadmap

- **Phase 1 (now):** official divisional PDFs, plus clearly labelled secondary sources where a zone hasn't published any.
- **Phase 2:** visitors record a short video at a station; Gemini checks the location and station boards and lists the facilities it sees. See [docs/phase-2-video-reports.md](docs/phase-2-video-reports.md).

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

Review the generated station names before committing. The parser detects the three layouts divisions use (feature lists, per-station blocks, and one-row-per-station grids). Useful options:

```bash
--pages 17-25                 # one division out of a multi-division PDF
--codes stations.json         # datameet station list, for PDFs that name stations by code
data/transcribed/x.json       # hand-transcribed rows for scanned pages, given like a PDF
```

Add new codes and alternate spellings to `data/station_names.json`.

## Deploying

Pushing to `main` runs the tests, rebuilds the data and publishes `site/` to GitHub Pages. One-time setup: **Settings → Pages → Source: GitHub Actions**.

## Corrections

Every station page has a "Something wrong or missing?" link that opens a GitHub issue for that station.

## Disclaimer

Not an official Indian Railways service. Facilities can change, so check with the station before relying on one. Data is from Indian Railways' published accessibility documents; each station page links its source and the date it was checked.
