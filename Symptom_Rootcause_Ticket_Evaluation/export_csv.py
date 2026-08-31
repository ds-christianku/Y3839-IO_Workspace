"""Exports all open Jira bug tickets with symptom/root cause assignment to CSV."""
import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).parent / "output"
OUT  = Path(__file__).parent / "output" / "ticket_export.csv"

jira_data   = json.loads((BASE / "symptom_analysis_jira.json").read_text(encoding="utf-8"))
jira_issues = json.loads((BASE / "jira_issues.json").read_text(encoding="utf-8"))
llm_cache   = json.loads((BASE / "llm_classifications.json").read_text(encoding="utf-8"))

EXCLUDED = {"Y3839-425", "Y3839-340", "Y3839-515"}
RESOLVED = {"Resolved", "Closed", "Done", "Won't Fix", "Rejected", "In QA"}


def strip_tags(text: str) -> str:
    return re.sub(r"\s*\[(HW|SW|FW)\]", "", text).strip()


# Collect assigned tickets from symptom data
assigned: dict[str, dict] = {}
for sym in jira_data["symptoms"]:
    sym_name = sym["name"]
    for rc in sym.get("root_causes_jira", []):
        rc_text = strip_tags(rc["text"])
        for ticket in rc.get("jira_tickets", []):
            assigned[ticket["key"]] = {"Symptom": sym_name, "Root Cause": rc_text}

rows = []

# All open bugs including excluded documentation tickets
open_bugs = [
    i for i in jira_issues
    if i.get("issuetype") == "Bug"
    and i.get("status", "") not in RESOLVED
]

for bug in open_bugs:
    key = bug["key"]
    if key in assigned:
        rows.append({
            "Ticket": key,
            "Summary": bug.get("summary", "")[:120],
            "Symptom": assigned[key]["Symptom"],
            "Root Cause": assigned[key]["Root Cause"],
        })
    else:
        rows.append({
            "Ticket": key,
            "Summary": bug.get("summary", "")[:120],
            "Symptom": "Unassigned",
            "Root Cause": "",
        })

rows.sort(key=lambda r: (r["Symptom"].lower(), r["Root Cause"].lower(), r["Ticket"]))

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["Ticket", "Summary", "Symptom", "Root Cause"])
    writer.writeheader()
    writer.writerows(rows)

assigned_count   = sum(1 for r in rows if r["Symptom"] != "Unassigned")
unassigned_count = sum(1 for r in rows if r["Symptom"] == "Unassigned")
print(f"Exported {len(rows)} rows to {OUT}")
print(f"  Assigned:   {assigned_count}")
print(f"  Unassigned: {unassigned_count}")
