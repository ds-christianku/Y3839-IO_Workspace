#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_05_jira_match.py
Matches Jira bugs to symptoms and root causes using weighted keyword scoring.
Edit MANUAL_ASSIGNMENTS below to force specific ticket→RC assignments.
"""

import json
import re
from pathlib import Path

BASE_DIR     = Path(__file__).parent
JIRA_PATH    = BASE_DIR / "output" / "jira_issues.json"
SYMPTOM_PATH = BASE_DIR / "output" / "symptom_analysis.json"
OUTPUT_PATH  = BASE_DIR / "output" / "symptom_analysis_jira.json"

ROOT_CAUSE_KEYWORDS = {
    "Not specified USB cable":                     (["usb cable", "cable spec"], ["cable length", "max range", "specification"]),
    "Loose micro-B USB interface":                 (["micro-b", "cable clip"], ["microbusb", "loose micro", "micro usb connector"]),
    "Loose USB3 remote/sensor interface":          (["loose", "loos", "usb3 remote"], ["connector loose", "interface loose", "not seated", "loose contact"]),
    "Loose sensor cable screws":                   (["screw", "loose screw"], ["cable screw", "screw loos", "fastening"]),
    "Defect USB3 remote (cold solder joints)":     (["cold solder", "dying box", "usb3 remote"], ["solder joint", "remote defect", "cold solder", "soldering"]),
    "Driver conflicts (CDR vs IOSS)":              (["driver conflict", "cdr twain", "driver"], ["cdr", "twain", "driver install", "coexistence"]),
    "Calibration file not transferred":            (["calibration", "calib file"], ["calibration transfer", "not transferred", "missing calibration"]),
    "Reconnection of sensor not stable":           (["reconnect", "reconnection"], ["reconnect fail", "reconnect unstable", "not stable after reconnect"]),
    "Missing error handling in SW/FW":             (["error handling", "exception"], ["unhandled exception", "missing error handling", "error not caught"]),
    "SW allocates too small buffer size":          (["buffer size", "buffer"], ["too small buffer", "buffer alloc", "buffer overflow", "dma buffer"]),
    "USB module defect":                           (["usb module", "dying box"], ["module defect", "module fail", "usb module broken"]),
    "Software timing error":                       (["timing error", "race condition"], ["timing issue", "timeout", "time out", "race"]),
    "Software can trigger a FPGA reset":           (["fpga reset", "fpga"], ["fpga trigger", "reset fpga", "unexpected reset"]),
    "More than one USB3 remote":                   (["multiple remote", "two remote"], ["double remote", "more than one remote", "second remote"]),
    "USB3 remote hardware failure":                (["remote fail", "usb3 remote", "dying"], ["no function", "hardware failure", "remote defect"]),
    "Electrostatic discharge (ESD)":               (["esd", "electrostatic"], ["discharge", "static electricity", "electrostatic"]),
    "Micro-B USB interface physically damaged":    (["micro-b", "physical damage"], ["damaged connector", "broken micro-b", "bent pin"]),
    "Voltage regulator (U12) broken":              (["u12", "voltage regulator"], ["vreg", "power supply", "voltage problem"]),
    "Firmware update bricked":                     (["bricked", "firmware update fail"], ["fw update", "update corrupted", "update brick", "rescue"]),
    "USB cable physically damaged":                (["cable damage", "broken cable"], ["cable defect", "cut cable", "damaged cable"]),
    "Mechanical wear":                             (["mechanical wear"], ["wear", "abrasion", "worn out"]),
    "Incorrect assembly":                          (["torque", "assembly"], ["wrong torque", "incorrect assembly", "screw torque"]),
    "Vibration / sensor handling":                 (["vibration"], ["shock", "vibrat", "handling loose"]),
    "Sensor self-triggering":                      (["self-trigger", "self trigger"], ["auto trigger", "spontaneous trigger", "trigger without exposure"]),
    "Sensor triggers by the influence of an electric field": (["electric field", "emf"], ["electromagnetic", "field influence", "emf trigger"]),
    "Sensor housing allows light to pass through": (["light leak", "housing"], ["light pass", "housing defect", "light ingress"]),
    "SW timing issue":                             (["timing", "ready signal"], ["exposure signal timing", "trigger timing", "ready for exposure"]),
    "Workflow sequence not correctly used by 3rd party": (["3rd party", "eaglesoft", "dentrix"], ["curve dental", "patterson", "third party workflow"]),
    "Incompatible PM software version":            (["pm software", "practice management"], ["compatible version", "version mismatch", "ioss compatible"]),
    "Network latency / IT infrastructure":         (["network latency", "slow network"], ["latency", "bandwidth", "it infrastructure", "network slow"]),
    "Circuit fault on the RAM":                (["ram circuit", "schematic"], ["ram error", "circuit design", "schematic mistake"]),
    "Power cycling the RAM during update":         (["power cycl", "power off during"], ["ram corr", "power loss update", "update power"]),
}

SYMPTOM_FILTERS = {
    "3rd Party Slowness (NAM)":                    ["slow", "lag", "latency", "performance", "ioss"],
    "Interface Update Issues":                      ["update", "firmware", "fw update", "rescue"],
    "Inconstant ready-for-exposure signaling (SW vs. Interface)": ["ready", "exposure", "trigger", "timing", "signal"],
    '"Dying Boxes" (USB module)':                  ["dying", "usb module", "remote fail", "no function", "esd", "power"],
    "No Power":                                    ["no power", "dead", "power fail", "not power"],
    "White Images":                                ["white image", "all white", "blank", "self-trigger", "white"],
    "Intermittent Connectivity":                   ["connect", "disconnect", "not detect", "intermittent", "reconnect"],
    "Images not transferred":                      ["not transfer", "acquiring", "capture", "no image", "buffer", "fpga"],
    "Loosening Screws":                            ["screw", "loos", "torque"],
    "Overexposed images":                          ["overexpos", "generator", "kv", "dose"],
    "Previous (Patient) Image":                    ["previous", "patient image", "ghost", "old image", "cache"],
}

# Manual overrides: symptom name → root cause text → list of forced Jira keys
MANUAL_ASSIGNMENTS = {
    "Images not transferred": {
        "SW allocates too small buffer size [SW]": ["Y3839-384"],
        "Software timing error [SW]": ["Y3839-547"],
        "Missing error handling in SW/FW [SW]": ["Y3839-282", "Y3839-513", "Y3839-520", "Y3839-523", "Y3839-529", "Y3839-555", "Y3839-570", "Y3839-593"],
    },
    "Inconstant ready-for-exposure signaling (SW vs. Interface)": {
        "Workflow sequence not correctly used by 3rd party SW [SW]": ["Y3839-639", "Y3839-631"],
        "SW timing issue [SW]": ["Y3839-382", "Y3839-524", "Y3839-533", "Y3839-545", "Y3839-567"],
    },
    "Interface Update Issues": {
        "Driver conflicts after IOSS/CDR reinstall [SW]": ["Y3839-673", "Y3839-710"],
        "Circuit fault on the RAM [HW]": ["Y3839-663"],
        "Missing error handling in SW/FW [SW]": ["Y3839-307", "Y3839-506", "Y3839-510", "Y3839-611", "Y3839-625", "Y3839-661", "Y3839-664", "Y3839-689", "Y3839-690", "Y3839-711"],
    },
    "Intermittent Connectivity": {
        "Calibration file not transferred correctly [SW]": ["Y3839-718"],
        "Loose micro-B USB interface (no cable clip used) [HW]": ["Y3839-383"],
        "Missing error handling in SW/FW [SW]": ["Y3839-373", "Y3839-471", "Y3839-478", "Y3839-479", "Y3839-521", "Y3839-522", "Y3839-537", "Y3839-538", "Y3839-594"],
        "Reconnection of sensor not stable [SW]": ["Y3839-231", "Y3839-305", "Y3839-526", "Y3839-599", "Y3839-691"],
        "Others currently unknown": ["Y3839-587", "Y3839-588"],
    },
    "Loosening Screws": {
        "Incorrect torque used during sensor cable exchange [HW]": ["Y3839-549"],
    },
    "Previous (Patient) Image": {
        "Missing error handling in SW/FW [SW]": ["Y3839-541", "Y3839-662"],
    },
    "White Images": {
        "Sensor self-triggering [HW]": ["Y3839-586"],
        "Sensor triggers by the influence of an electric field [HW]": ["Y3839-596"],
        "Sensor arming not disabled by SW/FW between image acquisition [SW]": ["Y3839-607", "Y3839-722"],
    },
    'No Power / "Dying Boxes" (USB module)': {
        "Others currently unknown": ["Y3839-695"],
    },
    "3rd Party Slowness (NAM)": {
        "Others currently unknown": ["Y3839-696"],
    },
}


def text_of(issue, field="both"):
    summary = (issue.get("summary") or "").lower()
    desc    = (issue.get("description") or "").lower()
    if field == "summary":
        return summary
    if field == "description":
        return desc
    return summary + " " + desc


def score_match(rc_text: str, issue: dict) -> int:
    """Returns relevance score: summary hits weighted 3×, description hits 1×."""
    rc_lower = rc_text.lower()
    score = 0
    for kw_prefix, (summary_kws, desc_kws) in ROOT_CAUSE_KEYWORDS.items():
        if kw_prefix.lower() not in rc_lower:
            continue
        summary = text_of(issue, "summary")
        desc    = text_of(issue, "description")
        for kw in summary_kws:
            if kw.lower() in summary:
                score += 3
        for kw in desc_kws:
            if kw.lower() in desc:
                score += 1
    return score


def run():
    print("=== Pipeline 05: Jira Match ===")

    if not JIRA_PATH.exists():
        print(f"ERROR: {JIRA_PATH} not found. Run pipeline_04_jira_import.py first.")
        return

    with open(JIRA_PATH, encoding="utf-8") as f:
        jira_issues = json.load(f)
    with open(SYMPTOM_PATH, encoding="utf-8") as f:
        analysis = json.load(f)

    RESOLVED = {"Resolved", "Closed", "Done", "Won't Fix", "Rejected", "In QA"}
    bugs = [i for i in jira_issues
            if i.get("issuetype") == "Bug"
            and i.get("status", "") not in RESOLVED]
    print(f"  Jira issues loaded: {len(jira_issues)} total, {len(bugs)} bugs/improvements")

    # Globally matched keys — starts with MANUAL_ASSIGNMENTS, grows per symptom (P1 first)
    globally_matched = {
        key
        for rc_map in MANUAL_ASSIGNMENTS.values()
        for keys in rc_map.values()
        for key in keys
    }

    for symptom in sorted(analysis["symptoms"], key=lambda s: (s.get("priority", 99), -s["total"])):
        sym_name   = symptom["name"]
        sym_filter = SYMPTOM_FILTERS.get(sym_name, [])
        relevant   = [i for i in bugs if any(kw in text_of(i) for kw in sym_filter)] if sym_filter else bugs
        manual_sym = MANUAL_ASSIGNMENTS.get(sym_name, {})
        jira_by_key = {i["key"]: i for i in bugs}
        root_causes = list(symptom.get("root_causes", []))
        # Add custom RCs from MANUAL_ASSIGNMENTS that aren't in the taxonomy
        for custom_rc in manual_sym:
            if custom_rc not in root_causes:
                ins = root_causes.index("Others currently unknown") if "Others currently unknown" in root_causes else len(root_causes)
                root_causes.insert(ins, custom_rc)
                symptom["root_causes"].insert(ins, custom_rc)

        best_rc_for: dict[str, tuple[str, int]] = {}
        for rc in root_causes:
            for issue in relevant:
                if issue["key"] in globally_matched:
                    continue
                s = score_match(rc, issue)
                if s > 0:
                    prev_rc, prev_s = best_rc_for.get(issue["key"], ("", 0))
                    if s > prev_s:
                        best_rc_for[issue["key"]] = (rc, s)
        for rc, forced_keys in manual_sym.items():
            for forced_key in forced_keys:
                best_rc_for[forced_key] = (rc, 99)

        rc_tickets: dict[str, list] = {rc: [] for rc in root_causes}
        for key, (rc, s) in best_rc_for.items():
            if rc in rc_tickets and key in jira_by_key:
                rc_tickets[rc].append((s, jira_by_key[key]))

        enriched_rcs = []
        for rc in root_causes:
            scored = sorted(rc_tickets[rc], key=lambda x: (-x[0], x[1]["key"]))
            enriched_rcs.append({
                "text": rc,
                "jira_tickets": [
                    {"key": i["key"], "summary": i["summary"][:100],
                     "status": i["status"], "priority": i["priority"],
                     "score": s, "url": i["url"]}
                    for s, i in scored
                ],
            })

        symptom["root_causes_jira"] = enriched_rcs
        total_matched = sum(len(r["jira_tickets"]) for r in enriched_rcs)
        print(f"  {sym_name}: {total_matched} Jira matches across {len(enriched_rcs)} root causes")
        for rc_data in enriched_rcs:
            for t in rc_data["jira_tickets"]:
                globally_matched.add(t["key"])

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Written: {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
