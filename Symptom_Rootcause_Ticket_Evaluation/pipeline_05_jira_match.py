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
import csv
import json
import re
import sys
import time
from pathlib import Path

BASE_DIR          = Path(__file__).parent
JIRA_PATH         = BASE_DIR / "output" / "jira_issues.json"
SYMPTOM_PATH      = BASE_DIR / "output" / "symptom_analysis.json"
SUMMARIES_PATH    = BASE_DIR / "output" / "jira_summaries.json"
LLM_CACHE_PATH    = BASE_DIR / "output" / "llm_classifications.json"
OUTPUT_PATH       = BASE_DIR / "output" / "symptom_analysis_jira.json"
TRAINING_PATH     = BASE_DIR / "training" / "Training-data.csv"

# Tickets excluded from the report (off-topic / documentation)
EXCLUDED_TICKETS: set[str] = {
    "Y3839-425",  # Outdated standards — documentation issue
    "Y3839-340",  # Missing document proof IEC/EN — documentation issue
    "Y3839-515",  # Binning not in requirements — documentation issue
}

# Tickets that must stay unassigned even if LLM/training suggests a mapping.
FORCED_UNASSIGNED_TICKETS: set[str] = {
    "Y3839-265",
}

BLOCKED_ROOT_CAUSE_KEYS: set[str] = {
    "ioss bug",
    "ioss bugs",
    "software timing error",
}


def _row_value(row: dict[str, str], *field_names: str) -> str:
    """Return first matching CSV field value (case-insensitive), trimmed."""
    lowered = {
        str(k).strip().lower(): ("" if v is None else str(v))
        for k, v in row.items()
        if k is not None
    }
    for name in field_names:
        value = lowered.get(name.strip().lower(), "")
        if value.strip():
            return value.strip()
    return ""


def _is_expected_unassigned(symptom: str, root_cause: str, note: str = "") -> bool:
    """Detect explicit unassigned markers from heterogeneous training exports."""
    s = (symptom or "").strip().lower()
    rc = (root_cause or "").strip().lower()
    n = (note or "").strip().lower()

    if s in {"", "unassigned", "not assigned", "n/a", "na"}:
        return True
    if "cannot be categorized" in n or "not assigned" in n:
        return True
    if "no impact" in s or "solved" in s:
        return True
    if not rc and s in {"not assigned", "unassigned"}:
        return True
    return False


def _normalize_symptom_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").casefold())


def _resolve_symptom_name(raw_symptom: str, symptom_names: list[str]) -> str | None:
    """Map training symptom labels to canonical analysis symptom names."""
    raw = (raw_symptom or "").strip()
    if not raw:
        return None

    alias_map = {
        "dyingboxes": 'No Power / "Dying Boxes" (USB module)',
        "inconstantreadyforexposuresignalingswvsinterface": "Inconstant/wrong signaling (SW vs. Interface)",
    }
    raw_key = _normalize_symptom_key(raw)
    if raw_key in alias_map:
        return alias_map[raw_key]

    by_exact = {name.casefold(): name for name in symptom_names}
    if raw.casefold() in by_exact:
        return by_exact[raw.casefold()]

    # Fallback: punctuation-insensitive comparison.
    by_norm = {_normalize_symptom_key(name): name for name in symptom_names}
    return by_norm.get(raw_key)


def load_expected_unassigned_keys(path: Path) -> set[str]:
    """Load training tickets that are explicitly expected to remain unassigned."""
    if not path.exists():
        return set()

    def _read_rows(encoding: str):
        with open(path, "r", encoding=encoding, newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))

    rows = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            rows = _read_rows(enc)
            break
        except UnicodeDecodeError:
            continue
    if rows is None:
        return set()

    expected = set()
    for row in rows:
        key = _normalize_ticket_key(_row_value(row, "Ticket", "Jira Ticket Key", "Ticket Key", "Issue Key", "Key"))
        if not key:
            continue

        symptom = _row_value(row, "expected symptom", "Symptom")
        root_cause = _row_value(row, "expected rootcause", "Root Cause", "Root cause")
        suggested = _row_value(row, "If AI Jira-Bug to Symptom assignment is not correct, which symptom and Root Cause fits better")

        if _is_expected_unassigned(symptom, root_cause, suggested):
            expected.add(key)

    return expected


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


def ask_llm(client, model: str, provider: str, base_url: str | None, prompt: str, timeout: int = 300) -> str:
    if client is None:
        # Native Ollama /api/chat — keep the request small and deterministic to avoid long reasoning delays.
        import urllib.request
        url = (base_url or "http://localhost:11434").rstrip("/v1").rstrip("/") + "/api/chat"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_predict": 2048,
                "num_ctx": 8192,
            },
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        rcs = [rc for rc in rcs if not _is_blocked_root_cause(str(rc))]
        if not rcs:
            continue
        lines.append(f"SYMPTOM: {sym_name}")
        for rc in rcs:
            lines.append(f"  RC: {rc}")
    return "\n".join(lines)


def ensure_unknown_last(root_causes: list[str]) -> list[str]:
    """Keep 'Others currently unknown' as the last root-cause entry."""
    if not root_causes:
        return root_causes
    normal = [rc for rc in root_causes if str(rc).strip().casefold() != "others currently unknown"]
    unknown = [rc for rc in root_causes if str(rc).strip().casefold() == "others currently unknown"]
    return normal + unknown


OFF_TOPIC_KEYWORDS = [
    "documentation", "applicable standards", "missing evidence", "ul 60601",
    "iec", "can/csa", "lokalisierung", "translation", "language", "sprach",
    "holder position", "rotation button", "installer", "recovery reference",
]


def _normalize_ticket_key(raw: str) -> str | None:
    if not raw:
        return None
    normalized = raw.strip().upper().replace("Y3839-Y", "Y3839-")
    m = re.search(r"Y3839-\d+", normalized, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(0).upper()


def _normalize_rc_key(text: str) -> str:
    """Normalize root-cause text for semantic comparison (ignore suffix tags/spacing)."""
    if not text:
        return ""
    cleaned = str(text).replace("(SW-solution)", "")
    cleaned = re.sub(r"\s*\[(HW|SW|FW|CM)\]\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned.lower()


def _strip_rc_label(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s*\[(HW|SW|FW|CM)\]\s*$", "", str(text), flags=re.IGNORECASE).strip()


def _infer_rc_label(base_text: str) -> str:
    t = (base_text or "").casefold()
    if not t:
        return "SW"
    if "sensor self-triggering" in t:
        return "HW"
    if any(k in t for k in ["torque", "assembly", "exchange", "user fault", "process"]):
        return "CM"
    if any(k in t for k in [
        "hardware", "usb", "remote", "sensor cable", "power", "electromagnetic", "solder",
        "x-ray generator", "alignment", "defect", "cold joint", "insufficient power", "loose"
    ]):
        return "HW"
    return "SW"


def _normalize_rc_with_label(text: str) -> str:
    """Return RC with canonical suffix [HW]/[SW]/[CM], mapping [FW] -> [SW]."""
    raw = (text or "").strip()
    if not raw:
        return ""
    if _normalize_rc_key(raw) == "others currently unknown":
        return "Others currently unknown"
    m = re.search(r"\[(HW|SW|FW|CM)\]\s*$", raw, flags=re.IGNORECASE)
    if m:
        label = m.group(1).upper()
        if label == "FW":
            label = "SW"
        return f"{_strip_rc_label(raw)} [{label}]"
    label = _infer_rc_label(raw)
    return f"{_strip_rc_label(raw)} [{label}]"


def _resolve_to_existing_rc(raw_rc: str, existing_root_causes: list[str]) -> str:
    """Resolve a raw RC text to an existing canonical RC by normalized key when possible."""
    target_key = _normalize_rc_key(raw_rc)
    for rc in existing_root_causes:
        if _normalize_rc_key(rc) == target_key:
            return rc
    return _normalize_rc_with_label(raw_rc)


def _is_blocked_root_cause(text: str) -> bool:
    return _normalize_rc_key(text) in BLOCKED_ROOT_CAUSE_KEYS


def load_training_rows(path: Path) -> list[dict[str, str]]:
    """Load normalized training rows from CSV."""
    if not path.exists():
        return []

    def _read_rows(encoding: str):
        with open(path, "r", encoding=encoding, newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))

    rows = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            rows = _read_rows(enc)
            break
        except UnicodeDecodeError:
            continue
    if rows is None:
        return []

    normalized: list[dict[str, str]] = []
    for row in rows:
        key = _normalize_ticket_key(_row_value(row, "Ticket", "Jira Ticket Key", "Ticket Key", "Issue Key", "Key"))
        title = _row_value(row, "Column2", "Summary", "Title")
        symptom = _row_value(row, "expected symptom", "Symptom")
        root_cause = _row_value(row, "expected rootcause", "Root Cause", "Root cause")

        if not key:
            continue
        if _is_expected_unassigned(symptom, root_cause):
            continue
        if not root_cause:
            continue
        if _is_blocked_root_cause(root_cause):
            continue

        normalized.append({
            "key": key,
            "title": title,
            "symptom": symptom,
            "root_cause": root_cause,
        })
    return normalized


def build_training_examples(training_rows: list[dict[str, str]], sym_map: dict, max_examples: int = 12) -> str:
    """Build compact few-shot examples for prompt conditioning."""
    lines: list[str] = []
    added = 0
    for row in training_rows:
        sym_name = row["symptom"]
        rc_text = row["root_cause"]
        if sym_name not in sym_map:
            continue
        if rc_text not in sym_map[sym_name].get("root_causes", []):
            continue
        title = (row.get("title") or "").strip()
        if len(title) > 120:
            title = title[:120].rstrip() + "..."
        lines.append(f"Beispiel {added + 1}:")
        lines.append(f"TICKET: {row['key']} | {title}")
        lines.append(f"SYMPTOM: {sym_name}")
        lines.append(f"ROOT_CAUSE: {rc_text}")
        lines.append("")
        added += 1
        if added >= max_examples:
            break
    return "\n".join(lines).strip()


def _is_training_mismatch(pred_sym: str, pred_rc: str, train_sym: str, train_rc: str) -> bool:
    """Return True if prediction differs from training label (RC compared normalized)."""
    if pred_sym != train_sym:
        return True
    return _normalize_rc_key(pred_rc) != _normalize_rc_key(train_rc)


def build_prompt(key: str, summary_title: str, ai_summary: str, taxonomy: str, training_examples: str = "") -> str:
    short_summary = (ai_summary or "").strip()
    if len(short_summary) > 500:
        short_summary = short_summary[:500].rstrip() + "..."
    examples_block = ""
    if training_examples:
        examples_block = (
            "Trainingsbeispiele (gelabelte historische Faelle, als Orientierung):\n"
            f"{training_examples}\n\n"
        )
    return (
        f"Du klassifizierst Jira-Tickets fuer das Y3839 USB3-Sensor-Interface-Projekt.\n\n"
        f"Ticket {key}: {summary_title[:180]}\n"
        f"KI-Zusammenfassung: {short_summary}\n\n"
        f"{examples_block}"
        f"Verfuegbare Symptome und Root Causes:\n{taxonomy}\n\n"
        f"Aufgabe:\n"
        f"Weise das Ticket dem passendsten Symptom und der passendsten Root Cause zu.\n"
        f"Wenn es eindeutig kein technisches Sensor-Problem ist, antworte exakt: KEIN_MATCH\n"
        f"Bei technischen Verbindungs-, Bild-, Update- oder Signal-Problemen: immer zuordnen.\n\n"
        f"Antwortformat (exakt):\n"
        f"SYMPTOM: <exakter Symptomname>\n"
        f"ROOT_CAUSE: <exakter Root-Cause-Text>\n\n"
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

def run(provider="ollama", model="gemma4:12b", base_url=None, force=False, batch_size: int = 5, timeout: int = 300):
    with open(JIRA_PATH, encoding="utf-8") as f:
        jira_issues = json.load(f)
    with open(SYMPTOM_PATH, encoding="utf-8") as f:
        analysis = json.load(f)

    # Apply training data: add missing root causes and provide few-shot examples.
    training_rows = load_training_rows(TRAINING_PATH)
    expected_unassigned_keys = load_expected_unassigned_keys(TRAINING_PATH)
    forced_unassigned_keys = set(FORCED_UNASSIGNED_TICKETS) | expected_unassigned_keys

    symptom_names = [sym["name"] for sym in analysis.get("symptoms", [])]
    for row in training_rows:
        resolved = _resolve_symptom_name(row.get("symptom", ""), symptom_names)
        if resolved:
            row["symptom"] = resolved

    sym_name_map = {sym["name"].casefold(): sym for sym in analysis.get("symptoms", [])}

    for sym in analysis.get("symptoms", []):
        normalized_rcs = []
        seen_keys = set()
        for rc in sym.get("root_causes", []):
            norm = _normalize_rc_with_label(str(rc))
            key = _normalize_rc_key(norm)
            if not key or key in seen_keys:
                continue
            normalized_rcs.append(norm)
            seen_keys.add(key)
        sym["root_causes"] = normalized_rcs

    training_added_root_causes = 0
    for row in training_rows:
        sym_name = row["symptom"]
        rc_text = row["root_cause"]
        sym = sym_name_map.get(sym_name.casefold())
        if not sym:
            continue
        root_causes = sym.setdefault("root_causes", [])
        rc_text = _resolve_to_existing_rc(rc_text, root_causes)
        row["root_cause"] = rc_text
        if rc_text not in root_causes:
            root_causes.append(rc_text)
            training_added_root_causes += 1

    for sym in analysis.get("symptoms", []):
        cleaned = [rc for rc in sym.get("root_causes", []) if not _is_blocked_root_cause(str(rc))]
        sym["root_causes"] = ensure_unknown_last(cleaned)

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
    training_examples = build_training_examples(training_rows, sym_map)
    training_examples_count = training_examples.count("Beispiel ")
    training_label_map = {
        row["key"]: (row["symptom"], row["root_cause"])
        for row in training_rows
        if row["symptom"] in sym_map and row["root_cause"] in sym_map[row["symptom"]].get("root_causes", [])
    }

    # Determine which tickets need LLM classification
    to_classify = [b for b in bugs
                   if b["key"] not in llm_cache
                   and b["key"] in ai_summaries
                   and b["key"] not in forced_unassigned_keys]

    print(f"=== Pipeline 05: Jira LLM Match === (provider={provider}, model={model})")
    print(f"  Open bugs:          {len(bugs)}")
    print(f"  Cached:             {len(llm_cache)}")
    print(f"  AI summaries:       {len(ai_summaries)}")
    print(f"  Training samples:   {training_examples_count}")
    print(f"  Training labels:    {len(training_label_map)}")
    print(f"  Forced unassigned:  {len(forced_unassigned_keys)}")
    print(f"  Added root causes:  {training_added_root_causes}")
    print(f"  -> To classify:      {len(to_classify)}")
    print(f"  -> Batch size:       {batch_size}")
    print(f"  -> Timeout:          {timeout}s\n")

    if to_classify:
        client = build_client(provider, model, base_url)
        overridden_during_classify = 0
        for start in range(0, len(to_classify), batch_size):
            batch = to_classify[start:start + batch_size]
            print(f"--- Batch {start // batch_size + 1} ({len(batch)} tickets) ---")
            for i, ticket in enumerate(batch, 1):
                key = ticket["key"]
                ai_sum = ai_summaries[key]
                prompt = build_prompt(key, ticket.get("summary", ""), ai_sum, taxonomy, training_examples)
                print(f"[{start + i:3}/{len(to_classify)}] {key}: {ticket.get('summary','')[:60]}", end=" ... ")
                try:
                    answer = ask_llm(client, model, provider, base_url, prompt, timeout=timeout)
                    sym_name, rc_text = parse_response(answer, sym_map)
                    train_pair = training_label_map.get(key)
                    if sym_name and rc_text and train_pair:
                        t_sym, t_rc = train_pair
                        if _is_training_mismatch(sym_name, rc_text, t_sym, t_rc):
                            sym_name, rc_text = t_sym, t_rc
                            overridden_during_classify += 1
                    if sym_name and rc_text:
                        llm_cache[key] = {"symptom": sym_name, "rc": rc_text, "raw": answer}
                        print(f"-> {sym_name[:30]} / {rc_text[:35]}")
                    else:
                        llm_cache[key] = {"symptom": None, "rc": None, "raw": answer}
                        print("-> KEIN_MATCH")
                except BaseException as e:
                    print(f"FEHLER: {e}")
                    llm_cache[key] = {"symptom": None, "rc": None, "raw": f"ERROR: {e}"}
                    time.sleep(2)
                    continue
                with open(LLM_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(llm_cache, f, indent=2, ensure_ascii=False)
            # short pause between batches so the local model can recover
            if start + batch_size < len(to_classify):
                time.sleep(2)
        if overridden_during_classify:
            print(f"  Training overrides during classify: {overridden_during_classify}")

    # ── Assemble output ──────────────────────────────────────────────────────
    assignments: dict[str, tuple[str, str, str]] = {}
    training_overrides_from_cache = 0

    for key, issue in jira_by_key.items():
        if key in forced_unassigned_keys:
            continue

        train_pair = training_label_map.get(key)
        result = llm_cache.get(key, {}) if isinstance(llm_cache, dict) else {}
        pred_sym = result.get("symptom")
        pred_rc = result.get("rc")

        # If LLM has no assignment (or was not run), fall back to training mapping.
        if not pred_sym or not pred_rc:
            if train_pair:
                t_sym, t_rc = train_pair
                t_rc = _resolve_to_existing_rc(t_rc, sym_map.get(t_sym, {}).get("root_causes", []))
                if not _is_blocked_root_cause(t_rc):
                    assignments[key] = (t_sym, t_rc, "training_override")
                    training_overrides_from_cache += 1
            continue

        pred_rc = _resolve_to_existing_rc(pred_rc, sym_map.get(pred_sym, {}).get("root_causes", []))
        if _is_blocked_root_cause(pred_rc):
            continue

        if train_pair:
            t_sym, t_rc = train_pair
            t_rc = _resolve_to_existing_rc(t_rc, sym_map.get(t_sym, {}).get("root_causes", []))
            if _is_training_mismatch(pred_sym, pred_rc, t_sym, t_rc):
                if not _is_blocked_root_cause(t_rc):
                    assignments[key] = (t_sym, t_rc, "training_override")
                    training_overrides_from_cache += 1
                continue

        assignments[key] = (pred_sym, pred_rc, "llm")

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
                "score": 99 if source in {"manual", "training_override"} else 75,
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
    total_training_override = sum(1 for _, _, src in assignments.values() if src == "training_override")
    total_llm    = sum(1 for _, _, src in assignments.values() if src == "llm")
    print(f"\n  Result: {total_manual} manual + {total_training_override} training_override + {total_llm} LLM = {total_manual + total_training_override + total_llm} total")
    if training_overrides_from_cache:
        print(f"  Training overrides from cache: {training_overrides_from_cache}")
    print(f"  Written: {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="ollama", choices=["ollama", "copilot", "openai"])
    parser.add_argument("--model",    default="gemma4:12b")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--force",    action="store_true", help="Re-classify all tickets")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of tickets to classify per chunk")
    parser.add_argument("--timeout", type=int, default=300, help="Per-ticket timeout in seconds for the LLM provider")
    args = parser.parse_args()
    run(provider=args.provider, model=args.model, base_url=args.base_url, force=args.force, batch_size=args.batch_size, timeout=args.timeout)
