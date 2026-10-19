#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_04_jira_import.py
Fetches open issues from the Y3839 Jira project and saves them as JSON.
Credentials are read from environment variables (never hardcoded).
"""

import json
import os
import re
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE_DIR  = Path(__file__).parent
OUTPUT    = BASE_DIR / "output" / "jira_issues.json"
JIRA_SYM_OUTPUT = BASE_DIR / "output" / "symptom_analysis_jira.json"

JIRA_BASE = "https://jira.dentsplysirona.com"
JQL       = "project=Y3839 AND statusCategory!=Done ORDER BY priority ASC"
FIELDS    = "*all"
MAX       = 200

RELEASE_SPRINT_NAMES = {"Y3839_QualityInitiative_R1"}


def _extract_sprint_candidates(value):
    """Extract real sprint names from Jira sprint object strings like `name=Y3839_QualityInitiative_R1`."""
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []

    matches = re.findall(r"name=([^,\]]+)", text)
    if matches:
        return [m.strip() for m in matches if m.strip()]

    if "Y3839_" in text:
        matches = re.findall(r"Y3839_[A-Za-z0-9_]+", text)
        if matches:
            return [m.strip() for m in matches if m.strip()]

    return [text] if text and any(token in text.lower() for token in ("qualityinitiative", "sprint", "y3839_")) else []


def _walk_values(value, out):
    """Recursively collect nested string values that may contain sprint metadata."""
    if isinstance(value, dict):
        for k, v in value.items():
            key_name = str(k).lower()
            if key_name in {"name", "value", "state", "startdate", "enddate", "id"}:
                if isinstance(v, str) and v.strip():
                    out.update(_extract_sprint_candidates(v))
            _walk_values(v, out)
        return
    if isinstance(value, list):
        for item in value:
            _walk_values(item, out)
        return
    if isinstance(value, tuple):
        for item in value:
            _walk_values(item, out)
        return
    if isinstance(value, str) and value.strip():
        out.update(_extract_sprint_candidates(value))


def extract_sprint_names(raw_sprints):
    """Extract Jira sprint names from the raw customfield payload or any nested field value."""
    names = set()
    if raw_sprints is None:
        return names

    if isinstance(raw_sprints, (list, tuple)):
        raw_items = list(raw_sprints)
    else:
        raw_items = [raw_sprints]

    for item in raw_items:
        if isinstance(item, dict):
            _walk_values(item, names)
            continue
        if isinstance(item, str):
            names.update(_extract_sprint_candidates(item))
            continue
        if item is not None:
            names.update(_extract_sprint_candidates(item))

    return {
        name.strip()
        for name in names
        if name and any(token in name.lower() for token in ("qualityinitiative", "sprint", "y3839_", "wontdo", "qi"))
    }


def get_credentials():
    # Jira Server/Data Center: Personal Access Token only (no email needed)
    token = os.environ.get("JIRA_TOKEN") or input("Jira Personal Access Token: ").strip()
    return token


def fetch_issues(token: str, jql: str = JQL) -> list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    start, issues = 0, []
    while True:
        url = (
            f"{JIRA_BASE}/rest/api/2/search"
            f"?jql={urllib.parse.quote(jql)}"
            f"&fields={FIELDS}"
            f"&maxResults={MAX}"
            f"&startAt={start}"
        )
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {e.reason}")
            raise
        batch = data.get("issues", [])
        issues.extend(batch)
        start += len(batch)
        print(f"  Fetched {start} / {data['total']} issues...")
        if start >= data["total"] or not batch:
            break
    return issues


def _load_existing_jira_issues() -> list:
    if not OUTPUT.exists():
        return []
    with open(OUTPUT, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _load_known_ticket_keys() -> list[str]:
    keys: list[str] = []
    seen = set()

    for issue in _load_existing_jira_issues():
        key = str(issue.get("key", "")).strip()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    if JIRA_SYM_OUTPUT.exists():
        with open(JIRA_SYM_OUTPUT, encoding="utf-8") as f:
            jira_sym_data = json.load(f)
        for symptom in jira_sym_data.get("symptoms", []) if isinstance(jira_sym_data, dict) else []:
            for rc in symptom.get("root_causes_jira", []) if isinstance(symptom, dict) else []:
                for ticket in rc.get("jira_tickets", []) if isinstance(rc, dict) else []:
                    key = str(ticket.get("key", "")).strip() if isinstance(ticket, dict) else ""
                    if key and key not in seen:
                        seen.add(key)
                        keys.append(key)

    return keys


def _fetch_known_issues(token: str, keys: list[str], batch_size: int = 50) -> list:
    issues = []
    for start in range(0, len(keys), batch_size):
        batch_keys = keys[start:start + batch_size]
        quoted_keys = ",".join(batch_keys)
        batch_jql = f"key in ({quoted_keys}) ORDER BY key ASC"
        issues.extend(fetch_issues(token, jql=batch_jql))
    return issues


def _merge_issue_updates(existing_issues: list, refreshed_issues: list) -> tuple[list, int]:
    refreshed_by_key = {
        str(issue.get("key", "")).strip(): issue
        for issue in refreshed_issues
        if isinstance(issue, dict) and str(issue.get("key", "")).strip()
    }
    merged = []
    updated = 0
    for issue in existing_issues:
        key = str(issue.get("key", "")).strip() if isinstance(issue, dict) else ""
        if key and key in refreshed_by_key:
            merged.append(refreshed_by_key[key])
            updated += 1
        else:
            merged.append(issue)
    return merged, updated


def _update_symptom_analysis_ticket_statuses(refreshed_issues: list) -> tuple[int, int]:
    if not JIRA_SYM_OUTPUT.exists():
        return 0, 0

    with open(JIRA_SYM_OUTPUT, encoding="utf-8") as f:
        jira_sym_data = json.load(f)

    refreshed_by_key = {
        str(issue.get("key", "")).strip(): issue
        for issue in refreshed_issues
        if isinstance(issue, dict) and str(issue.get("key", "")).strip()
    }

    touched = 0
    updated = 0
    for symptom in jira_sym_data.get("symptoms", []) if isinstance(jira_sym_data, dict) else []:
        if not isinstance(symptom, dict):
            continue
        for rc in symptom.get("root_causes_jira", []) or []:
            if not isinstance(rc, dict):
                continue
            tickets = rc.get("jira_tickets", [])
            if not isinstance(tickets, list):
                continue
            for ticket in tickets:
                if not isinstance(ticket, dict):
                    continue
                key = str(ticket.get("key", "")).strip()
                if not key or key not in refreshed_by_key:
                    continue
                touched += 1
                source = refreshed_by_key[key]
                for field in ("summary", "status", "priority", "assignee", "labels", "components", "sprint", "release_sprint", "url"):
                    old_value = ticket.get(field)
                    new_value = source.get(field)
                    if old_value != new_value:
                        ticket[field] = new_value
                        updated += 1

    with open(JIRA_SYM_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(jira_sym_data, f, ensure_ascii=False, indent=2)

    return touched, updated


def simplify(issues: list) -> list:
    result = []
    for i in issues:
        f = i.get("fields", {})
        sprint_names = sorted(extract_sprint_names(f))
        result.append({
            "key":         i["key"],
            "summary":     f.get("summary", ""),
            "description": (f.get("description") or "").strip(),
            "status":      (f.get("status") or {}).get("name", ""),
            "issuetype":   (f.get("issuetype") or {}).get("name", ""),
            "priority":    (f.get("priority") or {}).get("name", ""),
            "assignee":    (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "labels":      f.get("labels", []),
            "components":  [c["name"] for c in f.get("components", [])],
            "sprint":      sprint_names,
            "release_sprint": any(name in RELEASE_SPRINT_NAMES for name in sprint_names),
            "url":         f"{JIRA_BASE}/browse/{i['key']}",
        })
    return result


def run(status_only: bool = False):
    print("=== Pipeline 04: Jira Import ===")
    token = get_credentials()
    print(f"Fetching from: {JIRA_BASE}")
    if status_only:
        known_keys = _load_known_ticket_keys()
        print(f"Mode: status-only refresh for known tickets ({len(known_keys)} keys)\n")
        if not known_keys:
            print("No known Jira keys found in existing outputs. Nothing to update.")
            return
        refreshed = simplify(_fetch_known_issues(token, known_keys))
        existing_issues = _load_existing_jira_issues()
        simplified, updated_issue_count = _merge_issue_updates(existing_issues, refreshed)
        touched_tickets, updated_ticket_fields = _update_symptom_analysis_ticket_statuses(refreshed)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)
        print(f"✓ Updated {updated_issue_count} existing issues in: {OUTPUT}")
        print(f"✓ Refreshed {touched_tickets} embedded Jira tickets in: {JIRA_SYM_OUTPUT}")
        print(f"  Changed embedded ticket fields: {updated_ticket_fields}")
        return

    print(f"JQL: {JQL}\n")
    issues = fetch_issues(token)
    simplified = simplify(issues)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(simplified, f, ensure_ascii=False, indent=2)
    print(f"\n✓ {len(simplified)} issues saved to: {OUTPUT}")
    from collections import Counter
    by_type = Counter(i["issuetype"] for i in simplified)
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {t}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-only", action="store_true", help="Update only existing Jira ticket statuses and metadata without syncing new tickets")
    args = parser.parse_args()
    run(status_only=args.status_only)

