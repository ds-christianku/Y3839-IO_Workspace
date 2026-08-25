#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_07_jira_summarize.py
Generates AI summaries for all open Jira bugs. Summaries appear as
hover tooltips and in the bug detail modal in the HTML report.
Already-summarized tickets are skipped unless --force is used.

Usage:
  python pipeline_07_jira_summarize.py               # skip already summarized
  python pipeline_07_jira_summarize.py --force        # regenerate all
  python pipeline_07_jira_summarize.py --model llama3.1:8b
"""

import json
import pathlib

BASE_DIR      = pathlib.Path(__file__).parent
JIRA_PATH     = BASE_DIR / "output" / "jira_issues.json"
JIRA_SYM_PATH = BASE_DIR / "output" / "symptom_analysis_jira.json"
OUTPUT_PATH   = BASE_DIR / "output" / "jira_summaries.json"


def _summarize_ticket(client, model: str, key: str, issues: dict, assignments: dict) -> str:
    issue    = issues.get(key, {})
    summary  = issue.get("summary", "")
    desc     = (issue.get("description") or "")[:500].replace("\r\n", "\n").replace("\r", "\n")
    symptom, root_cause = assignments.get(key, ("", ""))

    if symptom and root_cause:
        context = (f"Zugeordnet zu Symptom: {symptom}\nRoot Cause: {root_cause}\n\n"
                   f"Erkläre knapp: Was ist das Problem? Warum passt der Root Cause?")
    else:
        context = "Erkläre knapp in 2-3 Sätzen: Was ist das Problem und was ist die vermutliche technische Ursache?"

    prompt = (
        f"Du erstellst eine kurze technische Zusammenfassung (2-3 Sätze, Deutsch) für einen Jira-Bug.\n\n"
        f"Ticket {key}: {summary}\n"
        f"Beschreibung (Auszug): {desc}\n\n"
        f"{context}\n"
        f"Antworte NUR mit der Zusammenfassung, ohne Einleitung."
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=4096,
    )
    return (resp.choices[0].message.content or "").strip()


def run(model: str = "gemma4:12b", base_url: str = "http://localhost:11434/v1", force: bool = False):
    from openai import OpenAI

    with open(JIRA_PATH, encoding="utf-8") as f:
        issues = {i["key"]: i for i in json.load(f)}
    with open(JIRA_SYM_PATH, encoding="utf-8") as f:
        jira_data = json.load(f)

    summaries = {}
    if OUTPUT_PATH.exists() and not force:
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            summaries = json.load(f)

    assignments: dict[str, tuple[str, str]] = {}
    for sym in jira_data.get("symptoms", []):
        for rc in sym.get("root_causes_jira", []):
            for t in rc.get("jira_tickets", []):
                assignments[t["key"]] = (sym["name"], rc["text"])

    RESOLVED = {"Resolved", "Closed", "Done", "Won't Fix", "Rejected", "In QA"}
    all_open_bugs = [i for i in issues.values()
                     if i.get("issuetype") == "Bug" and i.get("status", "") not in RESOLVED]
    to_process = [i["key"] for i in all_open_bugs if i["key"] not in summaries]

    print(f"=== Pipeline 07: Jira Summarize === (model={model})")
    print(f"  Offene Bugs gesamt:       {len(all_open_bugs)}")
    print(f"  Davon zugeordnet:         {len(assignments)}")
    print(f"  Bereits zusammengefasst:  {len(summaries)}")
    print(f"  → Zu verarbeiten:         {len(to_process)}\n")

    if not to_process:
        print("Nichts zu tun.")
        return

    client = OpenAI(api_key="ollama", base_url=base_url)

    for i, key in enumerate(to_process, 1):
        print(f"[{i:2}/{len(to_process)}] {key}: {issues.get(key,{}).get('summary','')[:60]}", end=" ... ", flush=True)
        try:
            summaries[key] = _summarize_ticket(client, model, key, issues, assignments)
            print("OK")
        except Exception as e:
            print(f"FEHLER: {e}")
        OUTPUT_PATH.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nFertig. {len(summaries)} Zusammenfassungen gespeichert: {OUTPUT_PATH}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model",     default="gemma4:12b")
    p.add_argument("--base-url",  default="http://localhost:11434/v1", dest="base_url")
    p.add_argument("--force",     action="store_true")
    args = p.parse_args()
    run(args.model, args.base_url, args.force)
