"""Stage 3: Liest tickets_classified.json und generiert den HTML-Report.

Wandelt das klassifizierte JSON in das Report-Format um und ruft render_html auf.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import os
sys.path.insert(0, os.getcwd())
from analyze_srq_qr_tickets_only_description import build_report_data, render_html


def _to_report_row(t: dict) -> dict:
    """Konvertiert ein klassifiziertes Ticket-Dict in das Format fuer build_report_data."""
    return {
        "Transaction Number": t["ticket_id"],
        "CreatedAt": t.get("created_at", ""),
        "Record Type": t.get("record_type", ""),
        "RecordTypeGroup": t.get("record_type_group", ""),
        "Category Level 2": t.get("category_level_2", ""),
        "Category Level 3": t.get("category_level_3", ""),
        "Category Level 4": t.get("category_level_4", t.get("cat4", "")),

        "Firmware Version": t.get("firmware", ""),
        "Description": t.get("description_text", ""),
        "Description Primary": t["primary"],
        "Description Secondary": t["secondary"],
        "Support Hub (old)": t.get("support_hub", ""),
        "Tickets": t.get("tickets", 1),
        "Region": t.get("region", ""),
        "Notes": t.get("notes_text", ""),
        "Clarity": t.get("clarity", "unclear"),
    }


def render(classified_path: Path, output_html: Path) -> None:
    print(f"Lese klassifizierte Daten: {classified_path}")
    payload = json.loads(classified_path.read_text(encoding="utf-8"))
    tickets = payload["tickets"]
    stats = payload.get("stats", {})
    print(f"  {len(tickets)} Tickets geladen")

    rows = [_to_report_row(t) for t in tickets]

    source_label = f"tickets_classified.json ({len(rows)} Tickets)"
    report_data = build_report_data(
        rows,
        file_name=source_label,
        generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    html = render_html(report_data)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")

    summary = report_data["summaries"]["ALL"]
    print(f"\nReport erstellt: {output_html.resolve()}")
    print(f"Datensaetze: {summary['rows']}  |  Ticket-Summe: {summary['tickets']}")
    if stats.get("notes_refined_total"):
        print(f"Notes-Refinements angewendet: {stats['notes_refined_total']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: tickets_classified.json → HTML-Report")
    parser.add_argument("--input", default="output/tickets_classified.json")
    parser.add_argument("--output", default="Ticket_Report_CSV.html")
    args = parser.parse_args()

    classified_path = Path(args.input)
    if not classified_path.exists():
        raise FileNotFoundError(f"Klassifizierte Daten nicht gefunden: {classified_path}  →  Erst Stage 2 ausfuehren.")

    render(classified_path, Path(args.output))


if __name__ == "__main__":
    main()
