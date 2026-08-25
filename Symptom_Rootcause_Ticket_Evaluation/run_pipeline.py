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
    4. Jira Import        — fetch issues from Y3839 Jira project
    5. Jira Match         — assign tickets to symptoms/root causes
    6. Jira LLM Classify  — AI-assisted classification (optional, slow)
    7. Jira Summarize     — AI summaries for all tickets (optional, slow)

Usage:
  python run_pipeline.py            # core only (stages 1-3)
  python run_pipeline.py --jira     # core + Jira import + match (stages 1-5)
  python run_pipeline.py --all      # all stages including LLM (very slow)
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
import pipeline_06_jira_llm_classify as stage6
import pipeline_07_jira_summarize as stage7


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jira", action="store_true", help="Run Jira import + match after core pipeline")
    parser.add_argument("--all",  action="store_true", help="Run all stages including LLM classify + summarize")
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
        stage5.run()
        print()

    stage3.run()

    if args.all:
        print()
        stage7.run()
        print()
        stage3.run()  # re-render with summaries

    elapsed = round(time.time() - t0, 1)
    print()
    print("=" * 60)
    print(f"  ✓ Pipeline complete  ({elapsed}s)")
    html = BASE_DIR / "output" / "Symptom_Trend_Report.html"
    print(f"  Report: {html}")
    print("=" * 60)


if __name__ == "__main__":
    main()
