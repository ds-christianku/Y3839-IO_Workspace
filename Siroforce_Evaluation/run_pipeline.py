"""Orchestrator: Fuehrt alle drei Pipeline-Stufen nacheinander aus.

Verwendung:
  python run_pipeline.py                        # Standard-Pfade
  python run_pipeline.py --output my_report.html
  python run_pipeline.py --skip-ingest          # Nur Stage 2+3 (Rohdaten bereits vorhanden)
  python run_pipeline.py --skip-classify        # Nur Stage 3 (klassifizierte Daten bereits vorhanden)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import pipeline_01_ingest as stage1
import pipeline_02_classify as stage2
import pipeline_03_render as stage3


def main() -> None:
    parser = argparse.ArgumentParser(description="Ticket-Analyse Pipeline: CSV + Excel → JSON → Klassifizierung → HTML")
    parser.add_argument("--input-dir",    default="input",                                             help="Verzeichnis mit EXPORT_RH_*.csv")
    parser.add_argument("--pattern",      default="EXPORT_RH_*.csv",                                 help="Glob-Muster fuer CSV-Dateien")
    parser.add_argument("--excel",        default="input/20260731_IO_Imaging_SFTickets.xlsx")
    parser.add_argument("--sheet",        default="IO 24Month")
    parser.add_argument("--categories",   default="categories.json",                                 help="Keyword-Konfiguration")
    parser.add_argument("--raw-json",     default="output/tickets_raw.json",                         help="Zwischen-Output Stage 1")
    parser.add_argument("--classified-json", default="output/tickets_classified.json",              help="Zwischen-Output Stage 2")
    parser.add_argument("--output",       default="Ticket_Report_CSV.html",                          help="Finaler HTML-Report")
    parser.add_argument("--batch-size",   type=int, default=500,                                     help="Anzahl Tickets pro LLM-Block")
    parser.add_argument("--skip-ingest",  action="store_true",                                       help="Stage 1 ueberspringen (Rohdaten bereits vorhanden)")
    parser.add_argument("--skip-classify",action="store_true",                                       help="Stage 1+2 ueberspringen (klassifizierte Daten vorhanden)")
    args = parser.parse_args()

    t_start = dt.datetime.now()

    # ── Stage 1: Ingest ──────────────────────────────────────────────────────
    raw_path = Path(args.raw_json)
    if args.skip_classify or args.skip_ingest:
        print(f"[Stage 1] Uebersprungen – verwende vorhandene Datei: {raw_path}")
    else:
        print(f"\n{'='*60}")
        print("[Stage 1] Einlesen: CSV + Excel → tickets_raw.json")
        print(f"{'='*60}")
        csv_files = sorted(Path(args.input_dir).glob(args.pattern))
        if not csv_files:
            raise FileNotFoundError(f"Keine CSV-Dateien in: {args.input_dir}/{args.pattern}")
        print(f"CSV-Dateien gefunden: {len(csv_files)}")
        tickets = stage1.ingest(csv_files, Path(args.excel), args.sheet)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ Gespeichert: {raw_path}  ({len(tickets)} Tickets)")

    # ── Stage 2: Klassifizierung ─────────────────────────────────────────────
    classified_path = Path(args.classified_json)
    if args.skip_classify:
        print(f"[Stage 2] Uebersprungen – verwende vorhandene Datei: {classified_path}")
    else:
        print(f"\n{'='*60}")
        print("[Stage 2] Klassifizierung: tickets_raw.json → tickets_classified.json")
        print(f"{'='*60}")
        raw_tickets = json.loads(raw_path.read_text(encoding="utf-8"))

        cat_path = Path(args.categories)
        if cat_path.exists():
            cfg = stage2.load_and_apply_categories(cat_path)
            stage1.apply_region_config(cfg)
            print(f"Keyword-Konfiguration geladen: {cat_path}")

        existing_tickets: list[dict] = []
        if classified_path.exists():
            try:
                existing_payload = json.loads(classified_path.read_text(encoding="utf-8"))
                existing_tickets = existing_payload.get("tickets", [])
            except Exception:
                existing_tickets = []

        batch = stage2.select_unclassified_batch(raw_tickets, existing_tickets, args.batch_size)
        if not batch:
            print(f"Keine neuen Tickets zum Klassifizieren. {len(existing_tickets)} bereits klassifizierte Tickets bleiben erhalten.")
            payload = {"tickets": existing_tickets, "stats": {"total": len(existing_tickets), "notes_refined_total": 0, "refined_by_primary": {}, "top_transitions": {}}}
            classified_path.parent.mkdir(parents=True, exist_ok=True)
            classified_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            classified, stats = stage2.classify_tickets(batch, existing_tickets=existing_tickets, batch_size=args.batch_size)
            merged = existing_tickets + classified
            print(f"Block: {len(batch)} Tickets klassifiziert; {len(existing_tickets)} bereits vorhanden; insgesamt {len(merged)}")
            print(f"Notes-Refinement: {stats['notes_refined_total']} / {stats['total']} Tickets")
            for tr, cnt in list(stats["top_transitions"].items())[:5]:
                pct = cnt / max(stats["notes_refined_total"], 1) * 100
                print(f"  {tr}: {cnt} ({pct:.1f}%)")

            payload = {"tickets": merged, "stats": stats}
            classified_path.parent.mkdir(parents=True, exist_ok=True)
            classified_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ Gespeichert: {classified_path}")

    # ── Stage 3: Render ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("[Stage 3] Render: tickets_classified.json → HTML")
    print(f"{'='*60}")
    stage3.render(classified_path, Path(args.output))

    elapsed = (dt.datetime.now() - t_start).total_seconds()
    print(f"\nPipeline abgeschlossen in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
