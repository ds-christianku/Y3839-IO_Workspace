#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_04_jira_import.py
Fetches open issues from the Y3839 Jira project and saves them as JSON.
Credentials are read from environment variables (never hardcoded).
"""

import json
import os
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE_DIR  = Path(__file__).parent
OUTPUT    = BASE_DIR / "output" / "jira_issues.json"

JIRA_BASE = "https://jira.dentsplysirona.com"
JQL       = "project=Y3839 AND statusCategory!=Done ORDER BY priority ASC"
FIELDS    = "summary,status,issuetype,priority,assignee,description,labels,components"
MAX       = 200


def get_credentials():
    # Jira Server/Data Center: Personal Access Token only (no email needed)
    token = os.environ.get("JIRA_TOKEN") or input("Jira Personal Access Token: ").strip()
    return token


def fetch_issues(token: str) -> list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    start, issues = 0, []
    while True:
        url = (
            f"{JIRA_BASE}/rest/api/2/search"
            f"?jql={urllib.parse.quote(JQL)}"
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


def simplify(issues: list) -> list:
    result = []
    for i in issues:
        f = i.get("fields", {})
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
            "url":         f"{JIRA_BASE}/browse/{i['key']}",
        })
    return result


def run():
    print("=== Pipeline 04: Jira Import ===")
    token = get_credentials()
    print(f"Fetching from: {JIRA_BASE}")
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
    run()

