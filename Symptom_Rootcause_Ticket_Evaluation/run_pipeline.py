#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py
Orchestrates all pipeline stages:

  Core pipeline (Siroforce field data):
    1. Ingest   — load and prepare raw tickets
    2. Analyze  — match symptoms via keyword patterns
    3. Render   — generate HTML trend report

  Jira pipeline (run separately as needed):
    4. Jira Import     — fetch issues from Y3839 Jira project
    7. Jira Summarize  — AI summaries per ticket via LLM (run once, cached)
    5. Jira Match      — assign tickets to symptoms/root causes via LLM
    3. Render          — re-render with Jira assignments

Usage:
  python run_pipeline.py            # core only (stages 1-3)
  python run_pipeline.py --jira     # core + Jira import + LLM match (stages 1-5)
  python run_pipeline.py --all      # all stages including summarize (very slow first run)
  python run_pipeline.py --force    # re-classify all tickets (ignore LLM cache)
"""

import sys
import time
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import pipeline_01_ingest as stage1
import pipeline_02_analyze as stage2
import pipeline_03_render as stage3
import pipeline_04_jira_import as stage4
import pipeline_05_jira_match as stage5
import pipeline_07_jira_summarize as stage7


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jira",  action="store_true", help="Run Jira import + LLM match after core pipeline")
    parser.add_argument("--all",   action="store_true", help="All stages including AI summarize (slow first run)")
    parser.add_argument("--force", action="store_true", help="Re-classify all tickets ignoring LLM cache")
    args = parser.parse_args()

    print("=" * 60)
    print("  Symptom Root Cause Ticket Evaluation Pipeline")
    print("=" * 60)
    t0 = time.time()

    stage1.run()
    print()
    stage2.run()
    print()

    if args.jira or args.all:
        stage4.run()
        print()
        if args.all:
            stage7.run()
            print()
        stage5.run(force=args.force)
        print()

    stage3.run()

    elapsed = round(time.time() - t0, 1)
    print()
    print("=" * 60)
    print(f"  Pipeline complete  ({elapsed}s)")
    html = BASE_DIR / "output" / "Symptom_Trend_Report.html"
    print(f"  Report: {html}")
    print("=" * 60)


if __name__ == "__main__":
    main()
