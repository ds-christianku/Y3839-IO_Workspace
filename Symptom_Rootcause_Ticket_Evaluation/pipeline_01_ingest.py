#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_01_ingest.py
Reads raw tickets and prepares them for symptom analysis.
"""

import json
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
RAW_TICKETS_PATH = BASE_DIR.parent / "Siroforce_Evaluation" / "output" / "tickets_raw.json"
OUTPUT_PATH = BASE_DIR / "output" / "tickets_ingested.json"


def run():
    print("=== Pipeline 01: Ingest ===")

    if not RAW_TICKETS_PATH.exists():
        raise FileNotFoundError(f"Raw tickets not found: {RAW_TICKETS_PATH}")

    with open(RAW_TICKETS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    tickets = []
    years = set()

    for t in raw:
        year = (t.get("created_at") or "")[:4]
        if not year.isdigit():
            continue
        years.add(year)
        tickets.append({
            "ticket_id":          t.get("ticket_id", ""),
            "created_at":         t.get("created_at", ""),
            "year":               year,
            "region":             t.get("region", "") or "",
            "support_hub":        t.get("support_hub", "") or "",
            "record_type_group":  t.get("record_type_group", "") or "",
            "description":        t.get("description_text", "") or "",
            "notes":              t.get("notes_text", "") or "",
        })

    dates = sorted(t["created_at"] for t in tickets if t["created_at"])
    date_min = dates[0] if dates else ""
    date_max = dates[-1] if dates else ""

    from collections import Counter
    tickets_per_year = dict(sorted(Counter(t["year"] for t in tickets).items()))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "meta": {
            "total": len(tickets),
            "years": sorted(years),
            "date_min": date_min,
            "date_max": date_max,
            "tickets_per_year": tickets_per_year,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": str(RAW_TICKETS_PATH),
        },
        "tickets": tickets,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Loaded {len(tickets):,} tickets  |  Years: {sorted(years)}")
    print(f"  Output: {OUTPUT_PATH}")
    return result


if __name__ == "__main__":
    run()

