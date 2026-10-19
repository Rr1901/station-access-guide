"""Accessibility features tracked by the guide.

Each feature has:
  key       - stable id used in JSON and the site
  label     - what users see
  patterns  - regexes that match the heading used for this feature in
              Indian Railways divisional accessibility PDFs
"""

FEATURES = [
    {"key": "wheelchair", "label": "Wheelchair available",
     "patterns": [r"is\s+wheel\s*chair\s+available"]},
    {"key": "wheelchair_booking", "label": "Wheelchair can be booked in advance",
     "patterns": [r"wheel\s*chair\s+be\s+booked(\s+online)?", r"booking\s+of\s+wheel\s*chair"]},
    {"key": "battery_car", "label": "Battery-operated car",
     "patterns": [r"battery\s+operated\s+cars?"]},
    {"key": "human_assistance", "label": "Porter / human assistance",
     "patterns": [r"^human\s+assistance", r"booking\s+of\s+human\s+assistance",
                  r"divyangjan\)?\s+sahayak", r"pwd.*sahayak"]},
    {"key": "lift", "label": "Lift / elevator",
     "patterns": [r"(accessible\s+)?lift\s*(/\s*elevator)?"]},
    {"key": "ramp_entry", "label": "Ramp at main entry",
     "patterns": [r"ramp\s+at\s+main\s+entry"]},
    {"key": "ramp_fob", "label": "Ramp at foot over bridge",
     "patterns": [r"ramp\s+at\s+foot\s+over\s+bridges?(\s*\(for\s+inter[- ]platform\s+transfer\))?"]},
    {"key": "accessible_toilet", "label": "Accessible toilet",
     "patterns": [r"divyang\s+friendly\s+toilets?(\s*/\s*s)?"]},
    {"key": "water_booth", "label": "Accessible drinking-water booth",
     "patterns": [r"divyang\s+friendly\s+water\s+booths?(\s*/\s*s)?"]},
    {"key": "parking", "label": "Reserved parking",
     "patterns": [r"dedicated\s+parking(\s+for\s+divyangjan)?"]},
    {"key": "help_booth", "label": "Help / enquiry booth",
     "patterns": [r"help\s+booth(\s*/\s*enquiry)?"]},
    {"key": "braille_signage", "label": "Braille signage",
     "patterns": [r"braille\s+signage"]},
    {"key": "boarding_ramp", "label": "Boarding ramp for coaches",
     "patterns": [r"boarding\s+ramp"]},
]

FEATURE_KEYS = [f["key"] for f in FEATURES]

# Status values written to the site JSON.
YES = "yes"                # station is named in the official list for this feature
NOT_LISTED = "not_listed"  # we have the COMPLETE official list and the station is not in it
UNKNOWN = "unknown"        # we don't have a complete list for this feature yet
