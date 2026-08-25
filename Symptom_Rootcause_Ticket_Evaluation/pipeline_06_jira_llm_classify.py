#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_06_jira_llm_classify.py
Uses an LLM to classify Jira tickets into symptoms/root causes.
Results are suggestions — review and add to MANUAL_ASSIGNMENTS in
pipeline_05_jira_match.py, then re-run pipeline_05 + pipeline_03.

Usage:
  python pipeline_06_jira_llm_classify.py                         # Ollama gemma4:12b
  python pipeline_06_jira_llm_classify.py --provider copilot
  python pipeline_06_jira_llm_classify.py --limit 10              # test
"""

import json
import sys
import time
import re
import types
import pathlib

BASE_DIR     = pathlib.Path(__file__).parent
JIRA_PATH    = BASE_DIR / "output" / "jira_issues.json"
SYMPTOM_PATH = BASE_DIR / "output" / "symptom_analysis_jira.json"
MATCH_PATH   = BASE_DIR / "pipeline_05_jira_match.py"
OUTPUT_PATH  = BASE_DIR / "output" / "llm_suggestions.json"


def _make_args(provider="ollama", model=None, base_url=None, limit=None, skip_already_matched=False):
    args = types.SimpleNamespace(
        provider=provider, model=model, base_url=base_url,
        limit=limit, skip_already_matched=skip_already_matched
    )
    if args.model is None:
        args.model = {"copilot": "gpt-4o", "openai": "gpt-4o-mini",
                      "claude": "claude-3-5-sonnet-20241022"}.get(args.provider, "gemma4:12b")
    if args.base_url is None and args.provider == "ollama":
        args.base_url = "http://localhost:11434/v1"
    return args


def _get_copilot_token() -> str:
    import os, subprocess
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("COPILOT_TOKEN")
    if env_token:
        return env_token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5, shell=True)
        tok = result.stdout.strip()
        if tok and result.returncode == 0 and len(tok) > 10:
            return tok
    except Exception:
        pass
    print("FEHLER: Kein GitHub Token gefunden. Setze $env:GITHUB_TOKEN oder nutze gh auth login.")
    sys.exit(1)


def build_client(args):
    if args.provider == "claude":
        from anthropic import Anthropic
        import os
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            print("FEHLER: ANTHROPIC_API_KEY nicht gesetzt.")
            sys.exit(1)
        return Anthropic(api_key=key)
    from openai import OpenAI
    if args.provider == "openai":
        import os
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            print("FEHLER: OPENAI_API_KEY nicht gesetzt.")
            sys.exit(1)
        return OpenAI(api_key=key)
    elif args.provider == "copilot":
        token = _get_copilot_token()
        return OpenAI(api_key=token, base_url="https://models.inference.ai.azure.com",
                      default_headers={"Authorization": f"Bearer {token}"})
    else:
        return OpenAI(api_key="ollama", base_url=args.base_url)


def ask_llm(client, args, prompt: str) -> str:
    if args.provider == "claude":
        response = client.messages.create(model=args.model, max_tokens=4096, temperature=0,
                                          messages=[{"role": "user", "content": prompt}])
        return response.content[0].text.strip()
    else:
        resp = client.chat.completions.create(model=args.model, max_tokens=4096, temperature=0,
                                              messages=[{"role": "user", "content": prompt}])
        return resp.choices[0].message.content.strip()


def load_data():
    with open(JIRA_PATH, encoding="utf-8") as f:
        issues = json.load(f)
    with open(SYMPTOM_PATH, encoding="utf-8") as f:
        symptoms = json.load(f)["symptoms"]
    return issues, symptoms


def get_reserved_keys():
    reserved = set()
    try:
        text = MATCH_PATH.read_text(encoding="utf-8")
        reserved = set(re.findall(r'"(Y3839-\d+)"', text))
    except Exception:
        pass
    return reserved


def get_auto_matched_keys(symptoms):
    keys = set()
    for sym in symptoms:
        for rc in sym.get("root_causes_jira", []):
            for t in rc.get("jira_tickets", []):
                if isinstance(t, dict):
                    keys.add(t.get("key", ""))
    return keys


def build_taxonomy_text(symptoms) -> str:
    lines = []
    for sym in symptoms:
        keywords = sym.get("keywords", [])
        kw_str = f" [Keywords: {', '.join(keywords[:6])}]" if keywords else ""
        lines.append(f"SYMPTOM: {sym['name']}{kw_str}")
        for rc in sym.get("root_causes_jira", []):
            if "others currently unknown" not in rc["text"].lower():
                lines.append(f"  RC: {rc['text']}")
    return "\n".join(lines)


def build_prompt(ticket: dict, taxonomy: str) -> str:
    summary    = ticket.get("summary", "")
    desc       = (ticket.get("description") or "")[:800].replace("\r\n", " ").replace("\n", " ")
    components = ", ".join(ticket.get("components", []) or [])
    priority   = ticket.get("priority", "")
    return (
        f"Du klassifizierst Jira-Tickets für das Y3839 USB3-Sensor-Interface Projekt.\n\n"
        f"Ticket {ticket['key']}:\n"
        f"  Summary: {summary}\n  Priority: {priority}\n  Components: {components}\n"
        f"  Description (Auszug): {desc}\n\n"
        f"Verfügbare Symptome und Root Causes:\n{taxonomy}\n\n"
        f"Aufgabe: Ordne das Ticket dem passendsten Symptom und der passendsten Root Cause zu.\n"
        f"Falls kein spezifischer Root Cause passt, aber ein Symptom eindeutig zutrifft, nutze SYMPTOM_ONLY.\n"
        f"Falls kein Bezug besteht, antworte mit KEIN_MATCH.\n\n"
        f"Antworte NUR in einem dieser Formate:\n\n"
        f"Format 1:\nSYMPTOM: <exakter Symptomname>\nROOT_CAUSE: <exakter Root-Cause-Text>\n\n"
        f"Format 2:\nSYMPTOM_ONLY: <exakter Symptomname>\n\nFormat 3:\nKEIN_MATCH"
    )


def _classify(args):
    print(f"=== Pipeline 06: Jira LLM Classify === (provider={args.provider}, model={args.model})")
    issues, symptoms = load_data()
    reserved  = get_reserved_keys()
    auto_keys = get_auto_matched_keys(symptoms)
    taxonomy  = build_taxonomy_text(symptoms)

    RESOLVED = {"Resolved", "Closed", "Done", "Won't Fix", "Rejected", "In QA"}
    _prio = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3, "Lowest": 4}
    bugs = sorted(
        [i for i in issues if i.get("issuetype") == "Bug" and i.get("status", "") not in RESOLVED],
        key=lambda x: _prio.get(x.get("priority", "Medium"), 99)
    )

    to_process = [b for b in bugs if b["key"] not in reserved and b["key"] not in auto_keys] \
        if args.skip_already_matched else bugs
    if args.limit:
        to_process = to_process[:args.limit]
    print(f"  Bugs gesamt: {len(bugs)} → Verarbeite: {len(to_process)}")
    if not to_process:
        print("Keine Tickets zu verarbeiten.")
        return

    client  = build_client(args)
    sym_map = {sym["name"]: sym for sym in symptoms}
    results, suggestions = [], {}

    print(f"\nVerarbeite {len(to_process)} Tickets...\n")
    for i, ticket in enumerate(to_process, 1):
        key = ticket["key"]
        print(f"[{i:3}/{len(to_process)}] {key}: {ticket.get('summary', '')[:60]}", end=" ... ")
        try:
            answer = ask_llm(client, args, build_prompt(ticket, taxonomy))
        except Exception as e:
            print(f"FEHLER: {e}")
            time.sleep(2)
            continue

        sym_name, rc_text, symptom_only = None, None, None
        for line in answer.splitlines():
            if line.startswith("SYMPTOM_ONLY:"):
                symptom_only = line[12:].strip().lstrip(":").strip()
            elif line.startswith("SYMPTOM:"):
                sym_name = line[8:].strip()
            elif line.startswith("ROOT_CAUSE:"):
                rc_text = line[11:].strip()

        if "KEIN_MATCH" in answer.upper() and not symptom_only and not sym_name:
            print("→ KEIN_MATCH"); results.append({"key": key, "match": None, "raw": answer}); continue

        if symptom_only and not rc_text:
            found = next((s for s in sym_map if s == symptom_only), None)
            if found:
                print(f"→ [Symptom] {found[:50]}")
                suggestions.setdefault(found, {}).setdefault("__SYMPTOM_ONLY__", []).append(key)
                results.append({"key": key, "symptom": found, "symptom_only": True, "raw": answer})
            else:
                print(f"→ [Symptom unbekannt] {symptom_only[:50]}")
                results.append({"key": key, "symptom_raw": symptom_only, "symptom_only": True, "raw": answer})
            continue

        if sym_name is None or rc_text is None:
            print("→ KEIN_MATCH"); results.append({"key": key, "match": None, "raw": answer}); continue

        found_sym = next((s for s in sym_map if s == sym_name), None)
        found_rc  = next((rc for rc in sym_map[found_sym].get("root_causes_jira", [])
                          if rc["text"] == rc_text), None) if found_sym else None

        if found_sym and found_rc:
            print(f"→ {found_sym[:30]} / {found_rc['text'][:40]}")
            suggestions.setdefault(found_sym, {}).setdefault(found_rc["text"], []).append(key)
            results.append({"key": key, "symptom": found_sym, "root_cause": rc_text, "raw": answer})
        elif found_sym:
            print(f"→ [Symptom] {found_sym[:30]} (RC nicht exakt: {rc_text[:30]})")
            suggestions.setdefault(found_sym, {}).setdefault("__SYMPTOM_ONLY__", []).append(key)
            results.append({"key": key, "symptom": found_sym, "root_cause_raw": rc_text, "symptom_only": True, "raw": answer})
        else:
            print(f"→ [unbekannt] {sym_name[:30]} / {rc_text[:40]}")
            results.append({"key": key, "symptom_raw": sym_name, "root_cause_raw": rc_text, "raw": answer})

        if args.provider == "openai":
            time.sleep(0.3)

    OUTPUT_PATH.write_text(json.dumps({"suggestions": suggestions, "details": results},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nErgebnisse gespeichert: {OUTPUT_PATH}")

    print("\n" + "="*70)
    print("VORGESCHLAGENE ERGÄNZUNGEN FÜR MANUAL_ASSIGNMENTS in pipeline_05_jira_match.py:")
    print("="*70)
    for sn, rc_dict in sorted(suggestions.items()):
        rc_only  = rc_dict.get("__SYMPTOM_ONLY__", [])
        real_rcs = {k: v for k, v in rc_dict.items() if k != "__SYMPTOM_ONLY__"}
        print(f'\n    # {sn}')
        if real_rcs:
            print(f'    "{sn}": {{')
            for rct, keys in sorted(real_rcs.items()):
                print(f'        "{rct}": [{", ".join(f"{chr(34)}{k}{chr(34)}" for k in sorted(keys))}],')
            print("    },")
        if rc_only:
            print(f'    # Symptom-only: [{", ".join(f"{chr(34)}{k}{chr(34)}" for k in sorted(rc_only))}]')

    matched = sum(1 for r in results if r.get("symptom") and r.get("root_cause"))
    sym_only = sum(1 for r in results if r.get("symptom_only"))
    no_match = sum(1 for r in results if r.get("match") is None and not r.get("symptom"))
    print(f"\nZusammenfassung: {matched} Symptom+RC | {sym_only} Symptom-only | {no_match} KEIN_MATCH")


def run(provider: str = "ollama", model: str | None = None, limit: int | None = None):
    _classify(_make_args(provider=provider, model=model, limit=limit))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="ollama", choices=["openai", "claude", "ollama", "copilot"])
    p.add_argument("--model",    default=None)
    p.add_argument("--base-url", default=None, dest="base_url")
    p.add_argument("--limit",    type=int, default=None)
    p.add_argument("--skip-already-matched", action="store_true", default=False, dest="skip_already_matched")
    _classify(p.parse_args())
