"""Process tickets month by month using a local Ollama model.

Workflow:
1. Load the raw ticket JSON.
2. Sort tickets by created_at month.
3. Start with the earliest month.
4. Process all tickets of that month and stop afterwards.
5. Write a per-month result JSON and print progress logs like: X/Y Tickets verarbeitet.

This script is designed for a local Ollama installation and does not require a cloud API.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")
DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def extract_json_object(text: str) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.I)
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(cleaned)):
        ch = cleaned[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start:idx + 1]
    match = re.search(r"\{.*\}", cleaned, re.S)
    return match.group(0) if match else None


def call_ollama_json(prompt: str, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL) -> dict | None:
    endpoint = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0.1},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    content = body.get("message", {}).get("content", "")
    if not content:
        return None

    json_text = extract_json_object(content)
    if not json_text:
        return None

    try:
        parsed = json.loads(json_text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def ticket_month(ticket: dict) -> str:
    created = str(ticket.get("created_at", "") or "").strip()
    if len(created) >= 7 and created[4] == "-":
        return created[:7]
    return "unknown"


def analyze_ticket(ticket: dict, model: str, base_url: str) -> dict:
    notes = normalize_text(ticket.get("notes_text") or ticket.get("notes") or "")
    description = normalize_text(ticket.get("description_text") or ticket.get("description") or "")
    problem_summary = normalize_text(ticket.get("problem_summary") or ticket.get("problem") or "")
    solution_summary = normalize_text(ticket.get("solution_summary") or ticket.get("solution") or "")

    prompt = (
        "You are a ticket analysis assistant. Analyze the ticket and return valid JSON only.\n"
        "Required keys: problem_summary, solution_summary, issue_theme, category_hint.\n"
        "Use concise German or English summaries depending on the ticket content.\n"
        "If a value is missing, use 'n.a.'.\n\n"
        f"Ticket ID: {ticket.get('ticket_id', 'n.a.')}\n"
        f"Created At: {ticket.get('created_at', 'n.a.')}\n"
        f"Description: {description}\n\n"
        f"Existing problem summary: {problem_summary}\n"
        f"Existing solution summary: {solution_summary}\n\n"
        f"Ticket notes:\n{notes[:6000]}"
    )

    result = call_ollama_json(prompt, model=model, base_url=base_url) or {}
    problem = str(result.get("problem_summary") or problem_summary or "n.a.").strip() or "n.a."
    solution = str(result.get("solution_summary") or solution_summary or "n.a.").strip() or "n.a."
    issue_theme = str(result.get("issue_theme") or "n.a.").strip() or "n.a."
    category_hint = str(result.get("category_hint") or "n.a.").strip() or "n.a."

    return {
        "ticket_id": ticket.get("ticket_id", ""),
        "created_at": ticket.get("created_at", ""),
        "problem_summary": problem,
        "solution_summary": solution,
        "issue_theme": issue_theme,
        "category_hint": category_hint,
    }


def load_tickets(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "tickets" in data:
            return list(data["tickets"])
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported ticket JSON structure in {path}")


def save_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def process_monthly_batch(
    tickets: list[dict],
    month: str,
    output_dir: str | Path,
    model: str,
    base_url: str,
) -> dict:
    month_tickets = [t for t in tickets if ticket_month(t) == month]
    total = len(month_tickets)
    results: list[dict] = []

    print(f"\n=== Monat {month}: {total} Tickets ===")
    for idx, ticket in enumerate(month_tickets, start=1):
        analyzed = analyze_ticket(ticket, model=model, base_url=base_url)
        results.append(analyzed)
        print(f"[{month}] {idx}/{total} Tickets verarbeitet ({idx / total * 100:.1f}%) | Ticket {ticket.get('ticket_id', 'n.a.')}")

    payload = {
        "month": month,
        "processed_total": total,
        "tickets": results,
        "summary": {
            "counts_by_issue_theme": dict(Counter(item["issue_theme"] for item in results).most_common(10)),
            "counts_by_category_hint": dict(Counter(item["category_hint"] for item in results).most_common(10)),
        },
    }

    out_path = Path(output_dir) / f"monthly_ollama_analysis_{month}.json"
    save_json(out_path, payload)
    print(f"Ergebnis gespeichert: {out_path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Process raw tickets month by month with a local Ollama model.")
    parser.add_argument("--input", type=str, default="output/tickets_raw.json", help="Path to the raw ticket JSON file.")
    parser.add_argument("--output-dir", type=str, default="output/monthly_ollama", help="Directory for monthly output files.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Local Ollama model name, e.g. gemma4:12b")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="Ollama base URL, default http://localhost:11434")
    parser.add_argument("--month", type=str, default="", help="Optional specific month to process, format YYYY-MM. If empty, the earliest month is used.")
    args = parser.parse_args()

    tickets = load_tickets(args.input)
    if not tickets:
        raise ValueError("No tickets found in input file.")

    months = sorted({ticket_month(t) for t in tickets if ticket_month(t) != "unknown"})
    if not months:
        raise ValueError("No valid created_at values found to determine month groups.")

    target_month = args.month.strip() or months[0]
    if target_month not in months:
        raise ValueError(f"Month {target_month} not found in ticket data. Available months: {months[:10]} ...")

    print(f"Verarbeite Monat: {target_month}")
    print(f"Zu verarbeitende Tickets: {sum(1 for t in tickets if ticket_month(t) == target_month)}")
    process_monthly_batch(tickets, target_month, args.output_dir, args.model, args.base_url)


if __name__ == "__main__":
    main()
