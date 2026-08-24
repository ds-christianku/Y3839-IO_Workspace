#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate market symptom analysis from ticket notes_text using keyword matching."""

import json
import re
from collections import Counter
from datetime import date

with open('output/tickets_raw.json', encoding='utf-8') as f:
    tickets = json.load(f)

# Build lookup of major_issue_theme from classified tickets
with open('output/tickets_classified.json', encoding='utf-8') as f:
    classified_list = json.load(f)['tickets']
theme_lookup = {t['ticket_id']: t.get('major_issue_theme', '') for t in classified_list}

TOTAL = len(tickets)

# Symptom → regex keywords matched against notes_text (case-insensitive)
SYMPTOM_MAPPING = {
    "Intermittent Connectivity": [
        r"intermittent", r"not connect", r"not detect", r"not recogni",
        r"sensor not found", r"disconnect", r"no longer connect",
        r"loses connection", r"lost connection",
    ],
    "Images not transferred": [
        r"image not transfer", r"images not transfer", r"not acquiring",
        r"cannot capture", r"no image", r"unable to acquire",
        r"image.{0,20}not.{0,20}show", r"capture fail",
    ],
    "Loosening Screws": [
        r"screw.{0,20}loos", r"loos.{0,20}screw", r"loos.{0,20}screw",
        r"screw.{0,20}strip", r"strip.{0,20}screw", r"screw.{0,20}fall",
        r"loosening screw",
    ],
    '"Dying Boxes" (USB module)': [
        r"dying box", r"usb module.{0,20}(fail|dead|replac|defect|broken|issue)",
        r"interface module.{0,20}(fail|dead|replac|defect|broken)",
        r"(2\.0|3\.0) remote.{0,20}(fail|dead|replac|defect|broken)",
        r"remote.{0,20}(fail|dead|replac|not.{0,10}work)",
        r"interface box.{0,20}(fail|dead|replac|defect)",
    ],
    "No Power": [
        r"no power", r"not power", r"dead on arrival",
    ],
    "White Images": [
        r"white image", r"all white", r"image.{0,20}white", r"white.{0,20}image",
        r"blank image", r"image without radiation",
    ],
    "Overexposed images": [
        r"overexpos", r"over.expos", r"too bright", r"overexposure",
        r"recommended generator setting", r"generator setting.{0,30}overexpos",
    ],
    "Previous (Patient) Image": [
        r"previous.{0,20}image", r"patient.{0,20}image", r"old image",
        r"prior image", r"last patient", r"ghost image",
    ],
    "Interface Update Issues": [
        r"interface update", r"firmware update",
        r"update.{0,20}fail", r"update.{0,20}issue",
    ],
    "Inconstant ready-for-exposure signaling (SW vs. Interface)": [
        r"ready.for.exposure", r"not ready", r"timing out",
        r"exposure signal", r"ready signal", r"inconstant.{0,20}signal",
        r"(sw|software).{0,20}(vs|versus).{0,20}interface",
    ],
    "3rd Party Slowness (NAM)": [
        r"slow", r"slowness", r"latency", r"lag",
        r"performance", r"takes .{0,20}seconds", r"wait until",
    ],
}

# All symptoms use full notes_text; slowness is already in the set for clarity
NOTES_TEXT_SYMPTOMS = set(SYMPTOM_MAPPING.keys())

def match_notes(ticket, patterns, field='description_text'):
    # Default: description_text (same as HTML); use 'notes_text' for full notes search
    text = (ticket.get(field, '') or '').lower()
    return any(re.search(p, text) for p in patterns)

results = {}
for symptom, patterns in SYMPTOM_MAPPING.items():
    if symptom in NOTES_TEXT_SYMPTOMS:
        # Use full notes_text for this symptom
        matched = [t for t in tickets if match_notes(t, patterns, field='notes_text')]
    else:
        matched = [t for t in tickets if match_notes(t, patterns)]
    results[symptom] = {
        "count": len(matched),
        "pct": len(matched) / TOTAL * 100,
        "keywords": patterns,
        "tickets": matched,
    }

# Groups
GROUPS = {
    "Group 1 — Connectivity / Sensor Recognition": [
        "Intermittent Connectivity",
        "Images not transferred",
        "Loosening Screws",
    ],
    "Group 2 — Power / Module Failure": [
        "\"Dying Boxes\" (USB module)",
        "No Power",
    ],
    "Other Symptoms": [
        "White Images",
        "Overexposed images",
        "Previous (Patient) Image",
        "Interface Update Issues",
        "Inconstant ready-for-exposure signaling (SW vs. Interface)",
        "3rd Party Slowness (NAM)",
    ],
}

# Year breakdown helper
def by_year(ticket_list):
    c = Counter(t.get('created_at', '')[:4] for t in ticket_list)
    return dict(sorted(c.items()))

# Markdown output
lines = []
lines.append("# Market Symptom Analysis")
lines.append(f"*Generated: {date.today()}*  ")
lines.append(f"*Total tickets in dataset: **{TOTAL:,}***")
lines.append("")
lines.append("---")
lines.append("")

# Per-group sections
for group_name, symptoms in GROUPS.items():
    group_tickets = []
    for s in symptoms:
        group_tickets.extend(results[s]["tickets"])
    group_total = len(group_tickets)
    group_pct = group_total / TOTAL * 100

    lines.append(f"## {group_name}")
    lines.append(f"**Group total: {group_total:,} tickets ({group_pct:.1f}% of all tickets)**")
    lines.append("")
    lines.append("| Symptom | Tickets | % of Total | Keywords (regex, in notes) |")
    lines.append("|---------|--------:|-----------:|---------------------------|")
    for s in symptoms:
        r = results[s]
        kw = ", ".join(f"`{k}`" for k in r["keywords"])
        lines.append(f"| {s} | {r['count']:,} | {r['pct']:.1f}% | {kw} |")
    lines.append("")

    # Year breakdown for group
    lines.append("<details>")
    lines.append(f"<summary>Year breakdown for {group_name}</summary>")
    lines.append("")
    years = sorted(set(t.get('created_at', '')[:4] for t in group_tickets))
    lines.append("| Symptom | " + " | ".join(years) + " |")
    lines.append("|---------|" + "|".join([":---:"] * len(years)) + "|")
    for s in symptoms:
        yr = by_year(results[s]["tickets"])
        row = " | ".join(str(yr.get(y, 0)) for y in years)
        lines.append(f"| {s} | {row} |")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append("---")
    lines.append("")

# Overall summary table
lines.append("## Overall Summary")
lines.append("")
lines.append("| Symptom | Tickets | % of Total |")
lines.append("|---------|--------:|-----------:|")
all_symptoms = [s for grp in GROUPS.values() for s in grp]
for s in all_symptoms:
    r = results[s]
    lines.append(f"| {s} | {r['count']:,} | {r['pct']:.1f}% |")

covered = sum(r["count"] for r in results.values())
lines.append(f"| **Total (mapped)** | **{covered:,}** | **{covered/TOTAL*100:.1f}%** |")
lines.append(f"| *Total tickets in dataset* | *{TOTAL:,}* | *100%* |")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## Notes")
lines.append("")
lines.append("- Matching is based on **keyword search in `notes_text`** (full ticket notes, case-insensitive regex).")
lines.append("- A ticket may match multiple symptoms if the notes contain keywords for several symptoms.")
lines.append("- The keyword patterns use regular expressions (case-insensitive).")

out_path = 'market/market_symptom_analysis.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Written: {out_path}")
print(f"Total tickets: {TOTAL}")
for s, r in results.items():
    print(f"  {r['count']:5d}  {s}")
