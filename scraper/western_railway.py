"""Build the Western Railway division files from secondary sources.

Western Railway hasn't published station-wise accessibility lists, so its
stations are pieced together from news reports of official figures, each fact
carrying its source and date (see README, "Western Railway").

    python scraper/western_railway.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "data" / "transcribed" / "gujarat_lifts_escalators_2023.json"
OUT = ROOT / "data" / "divisions"
RETRIEVED = "2026-10-20"

SOURCES = {
    "ls": ("Lok Sabha answer on lifts and escalators in Gujarat, as on 31 Jul 2023 (DeshGujarat, 11 Aug 2023)",
           "https://deshgujarat.com/2023/08/11/39-railway-stations-in-gujarat-have-escalators/"),
    "ab": ("DeshGujarat: PM inaugurates 18 Amrit Bharat stations in Gujarat (22 May 2025)",
           "https://deshgujarat.com/2025/05/22/pm-modi-inaugurates-18-amrit-bharat-railway-stations-in-gujarat/"),
    "cyi": ("DeshGujarat: Chhayapuri station gets escalators (27 Sep 2025)",
            "https://deshgujarat.com/2025/09/27/chhayapuri-railway-station-in-vadodara-gets-escalators-and-other-amenities/"),
    "rjt22": ("DeshGujarat: Rajkot station gets escalators and lifts (10 Jan 2022)",
              "https://deshgujarat.com/2022/01/10/rajkot-railway-station-gets-electronic-escalator-lift-other-facilities/"),
    "irctc": ("IRCTC e-wheelchair booking page (undated)", "https://www.irctctourism.com/wheelchair"),
    "adipres": ("Ahmedabad division presentation (undated, about 2020–21)",
                "https://www.readkong.com/page/ahmedabad-division-western-railway-2295689"),
}
LS = "Lok Sabha answer, as on 31 Jul 2023"

# Station (as named on the site) -> (division, code). Names from the 2023 table
# are mapped in TABLE_NAMES. Divisions marked * were placed by route, not
# confirmed in a source; see README.
STATIONS = {
    # Ahmedabad division
    "Ahmedabad": ("Ahmedabad", "ADI"), "Bhachau": ("Ahmedabad", ""), "Gandhidham": ("Ahmedabad", "GIMB"),
    "Mahesana": ("Ahmedabad", "MSH"), "New Bhuj": ("Ahmedabad", ""), "Bhuj": ("Ahmedabad", "BHUJ"),
    "Palanpur": ("Ahmedabad", "PNU"), "Sabarmati (MG)": ("Ahmedabad", ""), "Samakhiali": ("Ahmedabad", "SIOB"),
    "Vadnagar": ("Ahmedabad", ""),
    # Rajkot division
    "Rajkot": ("Rajkot", "RJT"), "Bhaktinagar": ("Rajkot", "BKNG"), "Dwarka": ("Rajkot", "DWK"),
    "Hapa": ("Rajkot", "HAPA"), "Jamnagar": ("Rajkot", "JAM"), "Khambhaliya": ("Rajkot", "KMBL"),  # *
    "Okha": ("Rajkot", "OKHA"), "Surendranagar": ("Rajkot", "SUNR"),  # * sources conflict
    "Wankaner": ("Rajkot", "WKR"), "Kanalus": ("Rajkot", ""),  # *
    "Jamwanthali": ("Rajkot", "WTJ"), "Morbi": ("Rajkot", "MVI"), "Mithapur": ("Rajkot", "MTHP"),  # *
    # Bhavnagar division
    "Bhavnagar Terminus": ("Bhavnagar", "BVC"), "Botad": ("Bhavnagar", "BTD"), "Gandhigram": ("Bhavnagar", "GG"),
    "Jetalsar": ("Bhavnagar", "JLR"), "Junagadh": ("Bhavnagar", "JND"), "Palitana": ("Bhavnagar", "PIT"),
    "Porbandar": ("Bhavnagar", "PBR"), "Veraval": ("Bhavnagar", "VRL"), "Jamjodhpur": ("Bhavnagar", "JDH"),  # *
    "Limbdi": ("Bhavnagar", "LM"), "Sihor": ("Bhavnagar", ""), "Rajula": ("Bhavnagar", "RLA"),  # *
    "Mahuva": ("Bhavnagar", "MHV"),
    # Vadodara division
    "Vadodara": ("Vadodara", "BRC"), "Anand": ("Vadodara", "ANND"), "Ankleshwar": ("Vadodara", "AKV"),
    "Chhayapuri": ("Vadodara", "CYI"), "Ekta Nagar": ("Vadodara", "EKNR"),  # *
    "Godhra": ("Vadodara", "GDA"), "Kosamba": ("Vadodara", "KSB"), "Nadiad": ("Vadodara", "ND"),
    "Karamsad": ("Vadodara", ""), "Dakor": ("Vadodara", "DK"), "Derol": ("Vadodara", "DRL"),  # *
    # Mumbai Central division
    "Surat": ("Mumbai Central", "ST"), "Udhna": ("Mumbai Central", "UDN"), "Vapi": ("Mumbai Central", "VAPI"),
    "Valsad": ("Mumbai Central", "BL"), "Navsari": ("Mumbai Central", "NVS"), "Uttran": ("Mumbai Central", ""),  # *
    "Mumbai Central": ("Mumbai Central", "MMCT"),
}
TABLE_NAMES = {"Ahmedabad Junction": "Ahmedabad", "Ekta Nagar(EKNR)": "Ekta Nagar", }
AMRIT_BHARAT = ["Uttran", "Kosamba", "Karamsad", "Dakor", "Derol", "Samakhiali", "Hapa", "Kanalus", "Jamwanthali",
                "Morbi", "Mithapur", "Okha", "Jamjodhpur", "Limbdi", "Palitana", "Sihor", "Rajula", "Mahuva"]
AB_NOTE = ("Redeveloped under the Amrit Bharat Station Scheme, inaugurated 22 May 2025. The report says the 18 "
           "redeveloped Gujarat stations got lifts, escalators and Divyangjan-friendly facilities, but not which "
           "station got what.")
METHOD_NOTE = ("Western Railway has not published a station-wise accessibility list for this division. "
               "These details are pieced together from the sources below, some several years old; "
               "they may have changed and don't say whether lifts are working. Anything else shows as \"No data yet\".")


def site_name(table_name: str) -> str:
    name = TABLE_NAMES.get(table_name, table_name)
    return re.sub(r"\s+(Jn|Junction)$", "", name)


def count(n: int, what: str, src: str) -> dict:
    if n == 0:
        return {"status": "no", "note": f"None listed ({src})"}
    return {"status": "yes", "note": f"{n} {what}{'s' if n > 1 else ''} ({src})"}


def collect() -> dict:
    """{division: {"features": {key: {station: item}}, "notes": {station: text}, "sources": set}}"""
    divs: dict = {}

    def put(station, key, item, src):
        div = divs.setdefault(STATIONS[station][0], {"features": {}, "notes": {}, "sources": set(), "stations": {}})
        div["stations"].setdefault(station, set()).add(src)
        div["sources"].add(src)
        if key:
            div["features"].setdefault(key, {})[station] = item

    num = lambda x: 0 if x in ("–", "-", "") else int(x)
    for row in json.loads(TABLE.read_text(encoding="utf-8"))["rows"]:
        st = site_name(row[3])
        put(st, "escalator", count(num(row[4]), "escalator", LS), "ls")
        put(st, "lift", count(num(row[5]), "lift", LS), "ls")

    # Later or more specific reports, applied over the 2023 counts
    put("Rajkot", "lift", {"status": "yes", "note": f"3 lifts ({LS}); on PF 2 and 3 (2022 report)"}, "rjt22")
    put("Rajkot", "escalator", {"status": "yes", "note": f"3 escalators ({LS}); on PF 1–3 (2022 report)"}, "rjt22")
    put("Chhayapuri", "escalator", {"status": "yes", "note": "On the new foot overbridge between PF 1 and 2, opened Sep 2025"}, "cyi")
    put("Bhuj", "lift", count(2, "lift", "division presentation, about 2020–21; may be out of date"), "adipres")
    put("Ahmedabad", "wheelchair_booking", {"status": "yes", "note": "IRCTC e-wheelchair: call 8287931890, collect at the concourse, book at least 6 hours ahead (IRCTC listing, undated)"}, "irctc")
    put("Mumbai Central", "wheelchair_booking", {"status": "yes", "note": "IRCTC e-wheelchair: call 7021092600, collect at the concourse, book at least 6 hours ahead (IRCTC listing, undated)"}, "irctc")

    for st in AMRIT_BHARAT:
        put(st, None, None, "ab")
        divs[STATIONS[st][0]]["notes"][st] = AB_NOTE
    return divs


def main() -> int:
    for name, d in sorted(collect().items()):
        order = [k for k in SOURCES if k in d["sources"]]
        doc = {
            "division": name, "zone": "Western Railway",
            "source_title": SOURCES[order[0]][0], "source_url": SOURCES[order[0]][1],
            "sources": [{"title": SOURCES[k][0], "url": SOURCES[k][1]} for k in order],
            "retrieved": RETRIEVED, "method": "secondary", "method_note": METHOD_NOTE,
            "features": {k: {"complete": False, "per_station": dict(sorted(v.items()))} for k, v in d["features"].items()},
            "station_notes": dict(sorted(d["notes"].items())),
            "station_codes": {s: STATIONS[s][1] for s in sorted(d["stations"]) if STATIONS[s][1]},
            # which of the sources mention each station, so a page lists only its own
            "station_sources": {s: [SOURCES[k][1] for k in SOURCES if k in d["stations"][s]] for s in sorted(d["stations"])},
        }
        path = OUT / f"{name.lower().replace(' ', '_')}.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}: {len(d['stations'])} stations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
