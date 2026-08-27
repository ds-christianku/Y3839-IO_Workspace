#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_05_jira_match.py
Assigns open Jira bugs to symptoms and root causes via LLM classification
of their AI summaries. LLM results are cached in output/llm_classifications.json.

Usage:
  python pipeline_05_jira_match.py                        # Ollama gemma4:12b
  python pipeline_05_jira_match.py --force                # re-classify all
  python pipeline_05_jira_match.py --model gemma4:12b
  python pipeline_05_jira_match.py --provider copilot
"""

import argparse
import json
import sys
import time
from pathlib import Path

BASE_DIR          = Path(__file__).parent
JIRA_PATH         = BASE_DIR / "output" / "jira_issues.json"
SYMPTOM_PATH      = BASE_DIR / "output" / "symptom_analysis.json"
SUMMARIES_PATH    = BASE_DIR / "output" / "jira_summaries.json"
LLM_CACHE_PATH    = BASE_DIR / "output" / "llm_classifications.json"
OUTPUT_PATH       = BASE_DIR / "output" / "symptom_analysis_jira.json"

# Tickets excluded from the report (off-topic / documentation)
EXCLUDED_TICKETS: set[str] = {
    "Y3839-425",  # Outdated standards — documentation issue
    "Y3839-340",  # Missing document proof IEC/EN — documentation issue
    "Y3839-515",  # Binning not in requirements — documentation issue
}


# ─── LLM helpers ─────────────────────────────────────────────────────────────

def _get_copilot_token() -> str:
    import os, subprocess
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("COPILOT_TOKEN")
    if token:
        return token
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5, shell=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    print("FEHLER: Kein GitHub Token gefunden. Setze $env:GITHUB_TOKEN oder nutze gh auth login.")
    sys.exit(1)


def build_client(provider: str, model: str, base_url: str | None):
    from openai import OpenAI
    if provider == "copilot":
        token = _get_copilot_token()
        return OpenAI(api_key=token, base_url="https://models.inference.ai.azure.com",
                      default_headers={"Authorization": f"Bearer {token}"})
    if provider == "openai":
        import os
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    # For Ollama: use native /api/chat directly to avoid thinking-token stripping in OpenAI layer
    return None  # signals use of native Ollama API


def ask_llm(client, model: str, provider: str, base_url: str | None, prompt: str) -> str:
    if client is None:
        # Native Ollama /api/chat — returns full response including after thinking tokens
        import urllib.request
        url = (base_url or "http://localhost:11434").rstrip("/v1").rstrip("/") + "/api/chat"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        return (data.get("message", {}).get("content") or "").strip()
    resp = client.chat.completions.create(
        model=model, temperature=0, max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return (resp.choices[0].message.content or "").strip()


def build_taxonomy(symptoms: list) -> str:
    """Build taxonomy preferring root_causes_jira (actual used RCs) over root_causes (full list)."""
    lines = []
    for sym in symptoms:
        sym_name = sym["name"]
        # Use root_causes_jira if available (from prior run), else fall back to root_causes
        jira_rcs = sym.get("root_causes_jira", [])
        if jira_rcs:
            rcs = [rc["text"] if isinstance(rc, dict) else rc for rc in jira_rcs]
        else:
            rcs = sym.get("root_causes", [])
        if not rcs:
            continue
        lines.append(f"SYMPTOM: {sym_name}")
        for rc in rcs:
            lines.append(f"  RC: {rc}")
    return "\n".join(lines)


OFF_TOPIC_KEYWORDS = [
    "documentation", "applicable standards", "missing evidence", "ul 60601",
    "iec", "can/csa", "lokalisierung", "translation", "language", "sprach",
    "holder position", "rotation button", "installer", "recovery reference",
]


def build_prompt(key: str, summary_title: str, ai_summary: str, taxonomy: str) -> str:
    return (
        f"Du klassifizierst Jira-Tickets fuer das Y3839 USB3-Sensor-Interface-Projekt (Dental-Roentgensensor).\n\n"
        f"Ticket {key}: {summary_title}\n"
        f"KI-Zusammenfassung: {ai_summary}\n\n"
        f"Verfuegbare Symptome und Root Causes:\n{taxonomy}\n\n"
        f"Aufgabe:\n"
        f"Weise das Ticket dem passendsten Symptom und der passendsten Root Cause zu.\n"
        f"Nutze die KI-Zusammenfassung -- insbesondere 'Die Ursache liegt...' -- als Hauptsignal.\n"
        f"Nutze KEIN_MATCH NUR wenn das Ticket eindeutig kein technisches Sensor-Problem ist "
        f"(z.B. Dokumentationsnachweis, Spracheinstellungen, Standards-Zertifizierung).\n"
        f"Bei allen technischen Verbindungs-, Bild-, Update- oder Signal-Problemen: immer klassifizieren.\n\n"
        f"Antwortformat (exakt, kein zusaetzlicher Text):\n"
        f"SYMPTOM: <exakter Symptomname aus der Liste>\n"
        f"ROOT_CAUSE: <exakter Root-Cause-Text aus der Liste>\n\n"
        f"oder:\nKEIN_MATCH"
    )


def parse_response(answer: str, sym_map: dict) -> tuple[str | None, str | None]:
    if "KEIN_MATCH" in answer.upper():
        return None, None
    sym_name, rc_text = None, None
    for line in answer.splitlines():
        line = line.strip()
        if line.startswith("SYMPTOM:"):
            sym_name = line[8:].strip()
        elif line.startswith("ROOT_CAUSE:"):
            rc_text = line[11:].strip()
    # Fuzzy-match: accept if name is contained in a known symptom
    if sym_name and sym_name not in sym_map:
        sym_name = next((s for s in sym_map if sym_name in s or s in sym_name), None)
    if sym_name and rc_text:
        valid_rcs = sym_map.get(sym_name, {}).get("root_causes", [])
        if rc_text not in valid_rcs:
            rc_text = next((rc for rc in valid_rcs if rc_text in rc or rc in rc_text), None)
    return sym_name, rc_text


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run(provider="ollama", model="gemma4:12b", base_url=None, force=False):
    with open(JIRA_PATH, encoding="utf-8") as f:
        jira_issues = json.load(f)
    with open(SYMPTOM_PATH, encoding="utf-8") as f:
        analysis = json.load(f)
    ai_summaries: dict[str, str] = {}
    if SUMMARIES_PATH.exists():
        with open(SUMMARIES_PATH, encoding="utf-8") as f:
            ai_summaries = json.load(f)

    # Load LLM classification cache
    llm_cache: dict[str, dict] = {}
    if LLM_CACHE_PATH.exists() and not force:
        with open(LLM_CACHE_PATH, encoding="utf-8") as f:
            llm_cache = json.load(f)

    RESOLVED = {"Resolved", "Closed", "Done", "Won't Fix", "Rejected", "In QA"}
    bugs = [i for i in jira_issues
            if i.get("issuetype") == "Bug"
            and i.get("status", "") not in RESOLVED
            and i["key"] not in EXCLUDED_TICKETS]
    jira_by_key = {i["key"]: i for i in bugs}

    # Build symptom map for validation
    sym_map = {sym["name"]: sym for sym in analysis["symptoms"]}
    taxonomy = build_taxonomy(analysis["symptoms"])

    # Determine which tickets need LLM classification
    to_classify = [b for b in bugs
                   if b["key"] not in llm_cache
                   and b["key"] in ai_summaries]

    print(f"=== Pipeline 05: Jira LLM Match === (provider={provider}, model={model})")
    print(f"  Open bugs:          {len(bugs)}")
    print(f"  Cached:             {len(llm_cache)}")
    print(f"  AI summaries:       {len(ai_summaries)}")
    print(f"  -> To classify:      {len(to_classify)}\n")

    if to_classify:
        client = build_client(provider, model, base_url)
        for i, ticket in enumerate(to_classify, 1):
            key = ticket["key"]
            ai_sum = ai_summaries[key]
            prompt = build_prompt(key, ticket.get("summary", ""), ai_sum, taxonomy)
            print(f"[{i:3}/{len(to_classify)}] {key}: {ticket.get('summary','')[:60]}", end=" ... ")
            try:
                answer = ask_llm(client, model, provider, base_url, prompt)
                sym_name, rc_text = parse_response(answer, sym_map)
                if sym_name and rc_text:
                    llm_cache[key] = {"symptom": sym_name, "rc": rc_text, "raw": answer}
                    print(f"-> {sym_name[:30]} / {rc_text[:35]}")
                else:
                    llm_cache[key] = {"symptom": None, "rc": None, "raw": answer}
                    print("-> KEIN_MATCH")
            except Exception as e:
                print(f"FEHLER: {e}")
                time.sleep(2)
                continue
            # Save cache after each ticket to survive interruptions
            with open(LLM_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(llm_cache, f, indent=2, ensure_ascii=False)

    # ── Assemble output ──────────────────────────────────────────────────────
    assignments: dict[str, tuple[str, str, str]] = {}

    for key, result in llm_cache.items():
        if key in jira_by_key and result.get("symptom") and result.get("rc"):
            assignments[key] = (result["symptom"], result["rc"], "llm")

    # Build symptom → rc → tickets structure
    rc_tickets: dict[str, dict[str, list]] = {
        sym["name"]: {rc: [] for rc in sym.get("root_causes", [])}
        for sym in analysis["symptoms"]
    }

    for key, (sym_name, rc_text, source) in assignments.items():
        if sym_name in rc_tickets and rc_text in rc_tickets[sym_name]:
            issue = jira_by_key[key]
            rc_tickets[sym_name][rc_text].append({
                "key": key,
                "summary": issue.get("summary", "")[:100],
                "status": issue.get("status", ""),
                "priority": issue.get("priority", ""),
                "score": 99 if source == "manual" else 75,
                "source": source,
                "url": issue.get("url", ""),
            })

    # Inject into analysis output
    enriched = json.loads(json.dumps(analysis))
    for sym in enriched["symptoms"]:
        sym_name = sym["name"]
        enriched_rcs = []
        for rc_text in sym.get("root_causes", []):
            tickets = sorted(rc_tickets.get(sym_name, {}).get(rc_text, []),
                             key=lambda t: (0 if t["source"] == "manual" else 1, t["key"]))
            enriched_rcs.append({"text": rc_text, "jira_tickets": tickets})
        sym["root_causes_jira"] = enriched_rcs

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    total_manual = sum(1 for _, _, src in assignments.values() if src == "manual")
    total_llm    = sum(1 for _, _, src in assignments.values() if src == "llm")
    print(f"\n  Result: {total_manual} manual + {total_llm} LLM = {total_manual + total_llm} total")
    print(f"  Written: {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="ollama", choices=["ollama", "copilot", "openai"])
    parser.add_argument("--model",    default="gemma4:12b")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--force",    action="store_true", help="Re-classify all tickets")
    args = parser.parse_args()
    run(provider=args.provider, model=args.model, base_url=args.base_url, force=args.force)
