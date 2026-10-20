"""Accessibility features tracked by the guide.

Each feature has:
  key       - stable id used in JSON and the site
  label     - what users see
  patterns  - regexes matched against the "Item" / "Name of facility" cell of
              Indian Railways divisional accessibility PDFs
"""

FEATURES = [
    {"key": "wheelchair", "label": "Wheelchair available",
     "patterns": [r"is\s+whe\w*\s*chair\s+available", r"^no\s+of\s+wheel\s*chairs", r"^wheel\s*chairs?$"]},
    {"key": "wheelchair_booking", "label": "Wheelchair can be booked in advance",
     "patterns": [r"whe\w*\s*chair\s+be\s+booked"]},
    {"key": "battery_car", "label": "Battery-operated car",
     "patterns": [r"battery\s+operated\s+car"]},
    {"key": "human_assistance", "label": "Porter / human assistance",
     "patterns": [r"human\s+assistance", r"sahayak"]},
    {"key": "lift", "label": "Lift / elevator",
     "patterns": [r"lift\s*/?\s*elevator", r"access\w*\s+lifts?", r"^lifts?$"]},
    {"key": "escalator", "label": "Escalator",
     "patterns": [r"^escalators?$"]},
    {"key": "ramp_entry", "label": "Ramp at main entry",
     "patterns": [r"ramp\s+at\s+main\s+entry", r"ramp\s+to\s+st\w*\s+building", r"standard\s+ramps?\s+at\s+(station|entrance)"]},
    {"key": "ramp_second", "label": "Ramp at second entry",
     "patterns": [r"ramp\s+at\s+second"]},
    {"key": "ramp_fob", "label": "Ramp at foot over bridge",
     "patterns": [r"ramp\s+at\s+(foot\s+over\s+bridge|fob)", r"ramp\s+in\s+fob", r"(subway|fob)\s+with\s+ramp"]},
    {"key": "accessible_toilet", "label": "Accessible toilet",
     "patterns": [r"divya\w*\s+friendly\s+toilet", r"^divyangjan\s+toilets", r"^toilet\b"]},
    {"key": "water_booth", "label": "Accessible drinking-water booth",
     "patterns": [r"divya\w*\s+friendly\s+water", r"low\s+height\s+water", r"drinking\s+water"]},
    {"key": "parking", "label": "Reserved parking",
     "patterns": [r"dedicated\s+parking", r"^divyang\w*\s+parking", r"^parking\b"]},
    {"key": "help_booth", "label": "Help / enquiry booth",
     "patterns": [r"help\s+booth", r"help\s+desk", r"may\s+i\s+help"]},
    {"key": "low_counter", "label": "Low-height ticket counter",
     "patterns": [r"low\s+(height|level)\s+ticket"]},
    {"key": "tactile_path", "label": "Tactile path for blind passengers",
     "patterns": [r"tactile\s+(tiles|guide)"]},  # not "warning tactile" at edges
    {"key": "braille_map", "label": "Audio / Braille map",
     "patterns": [r"brail+e?\s+map"]},
    {"key": "braille_signage", "label": "Braille signage",
     "patterns": [r"braille\s+signages?"]},
    {"key": "boarding_ramp", "label": "Boarding ramp for coaches",
     "patterns": [r"boarding\s+ramp"]},
]

FEATURE_KEYS = [f["key"] for f in FEATURES]

# Status values written to the site JSON.
YES = "yes"                # the official data says the station has it
NO = "no"                  # the official data explicitly says the station does not have it
NOT_LISTED = "not_listed"  # we have the COMPLETE official list and the station is not in it
UNKNOWN = "unknown"        # the official data doesn't tell us
