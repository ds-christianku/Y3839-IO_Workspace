import json
from pathlib import Path


def normalize_status(raw):
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s in {"OnHold", "InAnalysis", "InProgress", "Solved"}:
        return s
    upper = s.upper()
    if upper in {"IN PROGRESS", "IN QA"}:
        return "InProgress"
    if upper == "ACCEPTED":
        return "InAnalysis"
    if upper in {"SOLVED", "DONE", "RESOLVED", "CLOSED"}:
        return "Solved"
    if upper == "ONHOLD":
        return "OnHold"
    if upper in {"IN ANALYSIS", "IN ANALYISIS"}:
        return "InAnalysis"
    if upper in {"INPROGRESS", "IN_PROGRESS"}:
        return "InProgress"
    if upper in {"IN QUARANTINE", "QUARANTINE"}:
        return "OnHold"
    return "OnHold"


def normalize_ticket(item):
    if isinstance(item, dict):
        key = item.get("key") or item.get("jira_key") or item.get("issue") or item.get("id") or ""
        raw = item.get("jira_status")
        if raw is None:
            raw = item.get("jiraStatus")
        if raw is None:
            raw = item.get("status")
        if raw is None:
            raw = ""
        status = normalize_status(raw)
        return {
            "key": str(key),
            "status": status,
            "jira_status": "" if raw is None else str(raw),
        }
    if isinstance(item, str):
        raw = item
        return {"key": raw, "status": normalize_status(raw), "jira_status": raw}
    raw = item
    return {"key": str(raw), "status": normalize_status(raw), "jira_status": str(raw)}


p = Path("output/rc_status.json")
with p.open("r", encoding="utf-8") as f:
    data = json.load(f)

rc = data.get("rc_status", data)
if not isinstance(rc, dict):
    raise TypeError("rc_status is not a dict")

transformed = 0
for outer_key, outer_val in list(rc.items()):
    if not isinstance(outer_val, dict):
        continue
    for inner_key, inner_val in list(outer_val.items()):
        if not isinstance(inner_val, dict):
            continue
        if "jira_tickets" not in inner_val:
            continue

        tickets = inner_val["jira_tickets"]
        if isinstance(tickets, dict):
            normalized = []
            for key, raw in tickets.items():
                normalized.append({
                    "key": str(key),
                    "status": normalize_status(raw),
                    "jira_status": "" if raw is None else str(raw),
                })
        elif isinstance(tickets, list):
            normalized = []
            for item in tickets:
                entry = normalize_ticket(item)
                if not entry.get("key"):
                    continue
                if "status" not in entry or not entry["status"]:
                    entry["status"] = normalize_status(entry.get("jira_status"))
                normalized.append(entry)
        else:
            normalized = []

        inner_val["jira_tickets"] = normalized
        inner_val["status"] = ""
        transformed += 1

output = {"rc_status": rc}
with p.open("w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"TRANSFORMED_COUNT: {transformed}")
print("INTERMITTENT_CONNECTIVITY_IOSS_BUGS_SW:")
print(json.dumps(output["rc_status"].get("Intermittent Connectivity", {}).get("IOSS bugs [SW]"), ensure_ascii=False, indent=2))
