#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_02_analyze.py
Matches tickets to market symptoms using keyword patterns from market_symptom_analysis.md.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE_DIR = Path(__file__).parent
INPUT_PATH = BASE_DIR / "output" / "tickets_ingested.json"
OUTPUT_PATH = BASE_DIR / "output" / "symptom_analysis.json"

# Keywords sourced directly from market/market_symptom_analysis.md
SYMPTOMS = [
    {
        "name": "Intermittent Connectivity",
        "priority": 1,
        "group": "Connectivity / Sensor Recognition",
        "ai_category": "Connectivity/Recognition, Hardware Defect/Physical Damage",
        "root_causes": [
            "Not specified USB cable used to PC (above max. specified range) [CM]",
            "Loose micro-B USB interface (no cable clip used) [CM]",
            "Loose USB3 remote/sensor interface [HW]",
            "Loose sensor cable screws [CM]",
            "Defect USB3 remote (cold solder joints) [HW]",
            "Driver conflicts (CDR vs IOSS) [SW]",
            "Calibration file not transferred correctly [SW]",
            "Reconnection of sensor not stable [SW]",
            "Missing error handling in SW/FW [SW]",
            "Electromagnetic interference (EMI) on system [HW]",
            "Insufficient power-supply [HW]",
            "IOSS bugs [SW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"intermittent", r"not connect", r"not detect", r"not recogni",
            r"sensor not found", r"disconnect", r"no longer connect",
            r"loses connection", r"lost connection",
        ],
    },
    {
        "name": "Images not transferred",
        "priority": 2,
        "group": "Connectivity / Sensor Recognition",
        "ai_category": "Connectivity/Recognition, Software/Firmware/Driver",
        "root_causes": [
            "USB module defect [HW]",
            "Software timing error [SW]",
            "Software can trigger a FPGA reset [SW]",
            "Loose USB3 remote/sensor interface [HW]",
            "More than one USB3 remote connected to acquisition PC [CM]",
            "SW allocates too small buffer size [SW]",
            "Missing error handling in SW/FW [SW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"image not transfer", r"images not transfer", r"not acquiring",
            r"cannot capture", r"no image", r"unable to acquire",
            r"image.{0,20}not.{0,20}show", r"capture fail",
        ],
    },
    {
        "name": "Loosening Screws",
        "priority": 2,
        "group": "Connectivity / Sensor Recognition",
        "ai_category": "Connectivity/Recognition",
        "root_causes": [
            "Mechanical wear [HW]",
            "Incorrect assembly (wrong torque used) [HW]",
            "Incorrect torque used during sensor cable exchange [CM]",
            "Vibration / sensor handling loosens the connection [HW]",
            "Missing error handling Remote (FPGA) / Sensor (FPGA) [FW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"screw.{0,20}loos", r"loos.{0,20}screw", r"screw.{0,20}strip",
            r"strip.{0,20}screw", r"screw.{0,20}fall", r"loosening screw",
        ],
    },
    {
        "name": 'No Power / "Dying Boxes" (USB module)',
        "priority": 2,
        "group": "Power / Module Failure",
        "ai_category": "Hardware Defect/Physical Damage, Spare Parts/RMA/Logistics",
        "root_causes": [
            "USB3 remote hardware failure [HW]",
            "Electrostatic discharge (ESD) at the interfaces of the USB3 remote [HW]",
            "Micro-B USB interface physically damaged [HW]",
            "Voltage regulator (U12) broken [HW]",
            "Firmware update bricked the USB3 remote [SW]",
            "USB cable physically damaged [CM]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"dying box",
            r"usb module.{0,20}(fail|dead|replac|defect|broken|issue)",
            r"interface module.{0,20}(fail|dead|replac|defect|broken)",
            r"(2\.0|3\.0) remote.{0,20}(fail|dead|replac|defect|broken)",
            r"remote.{0,20}(fail|dead|replac|not.{0,10}work)",
            r"interface box.{0,20}(fail|dead|replac|defect)",
            r"no power", r"not power", r"dead on arrival",
        ],
    },
    {
        "name": "White Images",
        "priority": 3,
        "group": "Image Quality",
        "ai_category": "Imaging/Acquisition/Exposure, Hardware Defect/Physical Damage",
        "root_causes": [
            "Sensor defect [HW]",
            "Sensor self-triggering [HW]",
            "Sensor triggers by the influence of an electric field [HW]",
            "Sensor housing allows light to pass through [HW]",
            "Wrong alignment X-Ray generator and sensor (user fault)",
            "Wrong X-Ray generator power [HW]",
            "Sensor permanently armed (scattering X-Ray, background accumulation) [FW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"white image", r"all white", r"image.{0,20}white",
            r"white.{0,20}image", r"blank image", r"image without radiation",
        ],
    },
    {
        "name": "Overexposed images",
        "priority": 3,
        "group": "Image Quality",
        "ai_category": "Imaging/Acquisition/Exposure, Hardware Defect/Physical Damage",
        "root_causes": [
            "Wrong X-Ray generator settings [HW]",
            "Sensor sensitivity issue [HW]",
            "Error in the image processing path [SW]",
            "Different implementation for dark image substraction [SW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"overexpos", r"over.expos", r"too bright",
            r"overexposure", r"recommended generator setting",
            r"generator setting.{0,30}overexpos",
        ],
    },
    {
        "name": "Previous (Patient) Image",
        "priority": 1,
        "group": "Image Quality",
        "ai_category": "Imaging/Acquisition/Exposure, Software/Firmware/Driver",
        "root_causes": [
            "Loose USB3 remote/sensor interface [HW]",
            "Loose sensor cable screws [HW]",
            "Sensor cable damaged [HW]",
            "Workflow robustness [SW]",
            "Second (rescue) image transfer path in IOSS [SW]",
            "Missing error handling in SW/FW [SW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"previous.{0,20}image", r"patient.{0,20}image", r"old image",
            r"prior image", r"last patient", r"ghost image",
        ],
    },
    {
        "name": "Interface Update Issues",
        "priority": 4,
        "group": "Software / Update",
        "ai_category": "Software/Firmware/Driver, Installation/Setup/Upgrade",
        "root_causes": [
            "Circuit fault on the RAM [HW]",
            "Power cycling the RAM during update corrupts the update file [HW]",
            "Missing error handling in SW/FW [SW]",
            "Driver conflicts after IOSS/CDR reinstall for 3rd party [SW]",
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"interface update", r"firmware update",
            r"update.{0,20}fail", r"update.{0,20}issue",
        ],
    },
    {
        "name": "Inconstant/wrong signaling (SW vs. Interface)",
        "priority": 3,
        "group": "Software / Update",
        "ai_category": "Imaging/Acquisition/Exposure, Software/Firmware/Driver",
        "root_causes": [
            "SW timing issue [SW]",
            "Workflow sequence not correctly used by 3rd party SW [SW]",
            "State-machine mismatch in SW/FW (out-of-sync) [FW]",
            "Missing signals/state changes from USB3 remote to PC [FW]",
            "Others currently unknown",
        ],
        "hint": "Acquisition SW must correctly display the system status.",
        "search_field": "notes",
        "keywords": [
            r"ready.for.exposure", r"not ready", r"timing out",
            r"exposure signal", r"ready signal", r"inconstant.{0,20}signal",
            r"(sw|software).{0,20}(vs|versus).{0,20}interface",
        ],
    },
    {
        "name": "3rd Party Slowness (NAM)",
        "priority": 1,
        "group": "Software / Update",
        "ai_category": "Software/Firmware/Driver, Connectivity/Recognition",
        "root_causes": [
            "Others currently unknown",
        ],
        "search_field": "notes",
        "keywords": [
            r"slow", r"slowness", r"latency", r"lag",
            r"performance", r"takes .{0,20}seconds", r"wait until",
        ],
    },
]


def _match(ticket, symptom):
    field = symptom["search_field"]
    if field == "notes":
        text = ticket["notes"].lower()
    elif field == "description":
        text = ticket["description"].lower()
    else:
        text = (ticket["description"] + " " + ticket["notes"]).lower()
    return any(re.search(p, text) for p in symptom["keywords"])


def run():
    print("=== Pipeline 02: Analyze ===")

    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    tickets = data["tickets"]
    years = data["meta"]["years"]
    total = data["meta"]["total"]

    # Normalize helpers (used for total_breakdown and per-symptom breakdown)
    def norm_region(t):
        r = (t.get("region") or "").upper()
        h = (t.get("support_hub") or "").upper()
        if h == "US" or r == "US":
            return "US"
        if r == "EU":
            return "EU"
        return "REST"

    def norm_type(t):
        rt = (t.get("record_type_group") or "").upper()
        if "COMPLAINT" in rt:
            return "Complaint"
        if "INQUIRY" in rt:
            return "Inquiry"
        return "Rest"

    # Use fixed ai_category from symptom definition
    # Build total breakdown for ALL tickets (for KPI filter updates)
    total_breakdown = {}
    for t in tickets:
        reg = norm_region(t)
        typ = norm_type(t)
        total_breakdown.setdefault(reg, {}).setdefault(typ, 0)
        total_breakdown[reg][typ] += 1

    results = []
    # Each ticket is assigned to the highest-priority matching symptom only
    globally_matched: set = set()
    for symptom in sorted(SYMPTOMS, key=lambda s: (s.get("priority", 99), s["name"])):
        matched = [t for t in tickets if id(t) not in globally_matched and _match(t, symptom)]
        globally_matched.update(id(t) for t in matched)
        by_year = Counter(t["year"] for t in matched)
        by_region = Counter(t["region"] for t in matched)

        # Build breakdown: region -> type -> year -> count
        breakdown = {}
        for t in matched:
            reg = norm_region(t)
            typ = norm_type(t)
            yr  = t["year"]
            breakdown.setdefault(reg, {}).setdefault(typ, {}).setdefault(yr, 0)
            breakdown[reg][typ][yr] += 1

        trend_pct = None
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1]
            c1, c2 = by_year.get(y1, 0), by_year.get(y2, 0)
            if c1 > 0:
                trend_pct = round((c2 - c1) / c1 * 100, 1)

        results.append({
            "name":         symptom["name"],
            "priority":     symptom.get("priority", 99),
            "group":        symptom["group"],
            "ai_category":  symptom.get("ai_category", ""),
            "root_causes":  symptom.get("root_causes", []),
            "hint":         symptom.get("hint", ""),
            "search_field": symptom["search_field"],
            "keywords":     symptom["keywords"],
            "total":        len(matched),
            "pct_of_total": round(len(matched) / total * 100, 1) if total else 0,
            "by_year":      dict(sorted(by_year.items())),
            "by_region":    dict(sorted(by_region.items(), key=lambda x: -x[1])),
            "breakdown":    breakdown,
            "trend_pct":    trend_pct,
            "ticket_ids":   [t["ticket_id"] for t in matched],
        })
        print(f"  {len(matched):5d}  {symptom['name']}")

    output = {
        "meta": {
            "total_tickets": total,
            "years": years,
            "date_min": data["meta"].get("date_min", ""),
            "date_max": data["meta"].get("date_max", ""),
            "tickets_per_year": data["meta"].get("tickets_per_year", {}),
            "total_breakdown": total_breakdown,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "symptoms": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  Output: {OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    run()
