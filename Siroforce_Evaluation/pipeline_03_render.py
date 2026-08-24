"""Stage 3: Liest tickets_classified.json und generiert den HTML-Report.

Wandelt das klassifizierte JSON in das Report-Format um und ruft render_html auf.
"""
from __future__ import annotations
from pathlib import Path

import argparse
import datetime as dt
import json
import re
from collections import Counter, defaultdict

def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text == "#":
        return ""
    return re.sub(r"\s+", " ", text)


def counter_to_sorted_rows(counter: Counter, top_n: int | None = None) -> list[list[object]]:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if top_n is not None:
        items = items[:top_n]
    return [[name, int(value)] for name, value in items]


def summarize_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    total_rows = len(rows)
    total_tickets = sum(int(r["Tickets"]) for r in rows)

    by_record_type = Counter(normalize_text(r["Record Type"]) or "Unknown" for r in rows)
    by_cat3 = Counter(normalize_text(r["Category Level 3"]) or "Unknown" for r in rows)
    by_cat4 = Counter(normalize_text(r["Category Level 4"]) or "Unknown" for r in rows)
    by_desc_primary = Counter(normalize_text(r["Description Primary"]) or "Unknown" for r in rows)

    return {
        "rows": total_rows,
        "tickets": total_tickets,
        "record_types": counter_to_sorted_rows(by_record_type),
        "category_level_3": counter_to_sorted_rows(by_cat3, top_n=15),
        "category_level_4": counter_to_sorted_rows(by_cat4, top_n=15),
        "description_primary": counter_to_sorted_rows(by_desc_primary),
    }


def build_report_data(rows: list[dict[str, object]], file_name: str, generated_at: str) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    grouped["ALL"] = rows
    for row in rows:
        grouped[str(row["Region"])].append(row)

    summaries = {region: summarize_rows(region_rows) for region, region_rows in grouped.items()}

    rows_payload = [
        {
          "Transaction Number": str(r["Transaction Number"]),
            "CreatedAt": str(r["CreatedAt"]),
            "Record Type": str(r["Record Type"]),
            "RecordTypeGroup": str(r["RecordTypeGroup"]),
          "Category Level 2": str(r["Category Level 2"]),
            "Category Level 3": str(r["Category Level 3"]),
            "Category Level 4": str(r["Category Level 4"]),
          "Firmware Version": str(r["Firmware Version"]),
          "Description": str(r["Description"]),
          "Description Primary": str(r["Description Primary"]),
          "Description Secondary": str(r["Description Secondary"]),
            "Support Hub (old)": str(r["Support Hub (old)"]),
            "Tickets": int(r["Tickets"]),
            "Region": str(r["Region"]),
            "Language": str(r.get("Language", "")),
            "Notes": str(r.get("Notes", "")),
            "Clarity": str(r.get("Clarity", "")),
            "SparePartGroup": str(r.get("SparePartGroup", "")),
            "MajorIssueDomain": str(r.get("MajorIssueDomain", "")),
            "MajorIssueTheme": str(r.get("MajorIssueTheme", "")),
            "SolutionPath": str(r.get("SolutionPath", "")),
        }
        for r in rows
    ]

    return {
        "meta": {
            "source_file": file_name,
            "generated_at": generated_at,
        },
        "available_regions": ["ALL", "US", "EU", "REST"],
        "available_record_type_groups": ["COMPLAINT", "INQUIRY", "REST"],
        "summaries": summaries,
        "rows": rows_payload,
    }


def render_html(report_data: dict[str, object]) -> str:
    payload = json.dumps(report_data, ensure_ascii=True)

    return f"""<!doctype html>
<html lang=\"de\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>AI supported Siroforce Tickets Analysis IO Sensor systems</title>
  <style>
    :root {{
      --bg: #f2efe9;
      --card: #fffdf8;
      --ink: #1d2a34;
      --muted: #5e6b74;
      --accent: #0f766e;
      --accent-soft: #d8f2ef;
      --line: #d8d1c5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% 0%, #fff8e8 0%, transparent 38%),
        radial-gradient(circle at 90% 15%, #d6efe9 0%, transparent 42%),
        var(--bg);
    }}
    .wrap {{ width: 100%; max-width: none; margin: 1rem 0; padding: 0 1rem; }}
    .header {{
      background: linear-gradient(140deg, #0f766e, #155e75);
      color: #f9fcfc;
      border-radius: 18px;
      padding: 1rem 1.25rem 1.1rem;
      box-shadow: 0 8px 30px rgba(18, 62, 68, 0.25);
    }}
    .header h1 {{ margin: 0; font-size: 1.35rem; line-height: 1.2; }}
    .header p {{ margin: 0.35rem 0 0; opacity: 0.92; font-size: 0.92rem; }}
    .header-meta {{
      margin: 0.35rem 0 0;
      font-size: 0.92rem;
      color: #e8f5f5;
      opacity: 0.98;
    }}
    .header-meta strong {{ color: #ffffff; }}
    .toolbar {{
      margin-top: 0.85rem;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.8rem;
    }}
    .toolbar-break {{
      flex-basis: 100%;
      width: 0;
      height: 0;
    }}
    label {{ font-weight: 600; }}
    select {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 10px;
      padding: 0.55rem 0.8rem;
      font-size: 1rem;
    }}
    .cards {{
      margin-top: 1rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 0.85rem;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 1rem;
    }}
    .kpi {{ font-size: 1.7rem; font-weight: 700; color: var(--accent); margin-top: 0.25rem; }}
    .kpi-subline {{ font-size: 0.95rem; font-weight: 600; color: var(--muted); margin-top: 0.2rem; line-height: 1.25; }}
    .muted {{ color: var(--muted); font-size: 0.95rem; }}
    .time-range-label {{ color: #ffffff; font-weight: 700; white-space: nowrap; display: block; margin-left: 0.35rem; font-size: 0.92rem; }}
    .grid {{
      margin-top: 1rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 0.85rem;
    }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
    }}
    .panel h3 {{
      margin: 0;
      padding: 0.75rem 1rem;
      background: var(--accent-soft);
      border-bottom: 1px solid var(--line);
      font-size: 1rem;
    }}
    .panel-body {{ padding: 0.8rem 1rem 1rem; }}
    .chart-toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 0.8rem;
    }}
    .bar-chart {{ display: grid; gap: 0.5rem; }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(150px, 240px) 1fr auto;
      gap: 0.55rem;
      align-items: center;
    }}
    .bar-label {{ font-size: 0.9rem; color: var(--ink); }}
    .bar-track {{
      height: 16px;
      border-radius: 999px;
      background: #e8ecef;
      overflow: hidden;
      border: 1px solid #d2dbe0;
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, #0f766e, #155e75);
    }}
    .pie-wrap {{
      margin-top: 0.9rem;
      border: 1px solid #ece6da;
      border-radius: 10px;
      background: #fff;
      padding: 1rem;
    }}
    .pie-canvas-holder {{
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 420px;
      padding: 0.8rem 1.2rem;
      position: relative;
    }}
    .pie-canvas {{
      width: 300px;
      height: 300px;
      max-width: 100%;
    }}
    .pie-notes-layer {{
      position: absolute;
      inset: 0;
      pointer-events: none;
    }}
    .pie-callout-layer {{
      position: absolute;
      inset: 0;
      pointer-events: none;
      overflow: visible;
    }}
    .pie-callout-line {{
      stroke: #4e6e7a;
      stroke-width: 1.4;
      stroke-linecap: round;
      opacity: 0.82;
    }}
    .pie-callout-handle {{
      fill: #ffffff;
      stroke: #2f6f8f;
      stroke-width: 1.4;
      cursor: grab;
      pointer-events: all;
    }}
    .pie-callout-handle:active {{
      cursor: grabbing;
    }}
    .pie-note {{
      position: absolute;
      min-width: 120px;
      min-height: 68px;
      max-width: 220px;
      max-height: 200px;
      background: #fff;
      border: 1px solid #c9dedb;
      border-radius: 8px;
      box-shadow: 0 4px 14px rgba(20, 53, 59, 0.16);
      pointer-events: auto;
      overflow: hidden;
      resize: both;
    }}
    .pie-note-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.2rem 0.35rem;
      background: #d8f2ef;
      border-bottom: 1px solid #c9dedb;
      cursor: move;
      user-select: none;
      font-size: 0.75rem;
      color: #28565f;
    }}
    .pie-note-delete {{
      border: 0;
      background: transparent;
      color: #5e6b74;
      font-size: 0.9rem;
      line-height: 1;
      cursor: pointer;
      padding: 0 0.2rem;
    }}
    .pie-note-delete:hover {{ color: #a64040; }}
    .pie-note-text {{
      padding: 0.35rem 0.45rem;
      min-height: 1.8rem;
      height: calc(100% - 25px);
      font-size: 0.82rem;
      color: var(--ink);
      outline: none;
      white-space: pre-wrap;
      word-break: break-word;
      overflow: auto;
    }}
    .pie-note-toolbar {{
      margin-top: 0.5rem;
      display: flex;
      gap: 0.45rem;
      flex-wrap: wrap;
    }}
    .pie-note-btn {{
      border: 1px solid #c7d2d9;
      background: #fff;
      color: #2f3f49;
      border-radius: 8px;
      padding: 0.35rem 0.55rem;
      font-size: 0.8rem;
      cursor: pointer;
    }}
    .pie-note-btn:hover {{ background: #f3f8f7; }}
    .pie-legend {{
      margin-top: 0.55rem;
      display: grid;
      gap: 0.35rem;
      font-size: 0.86rem;
    }}
    .pie-legend-row {{
      display: grid;
      grid-template-columns: 12px 1fr auto;
      gap: 0.45rem;
      align-items: center;
    }}
    .pie-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
    }}
    .pie-label {{
      color: var(--ink);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .pie-value {{
      color: var(--muted);
      font-weight: 600;
      white-space: nowrap;
    }}
    .line-wrap {{
      margin-top: 0.9rem;
      border: 1px solid #ece6da;
      border-radius: 10px;
      background: #fff;
      padding: 0.7rem;
      max-width: 1220px;
      margin-left: auto;
      margin-right: auto;
    }}
    .line-canvas-holder {{
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 340px;
    }}
    .line-canvas {{
      width: 100%;
      height: auto;
      max-width: 100%;
      display: block;
    }}
    .line-legend {{
      margin-top: 0.6rem;
      display: grid;
      gap: 0.35rem;
      font-size: 0.86rem;
      max-width: 1220px;
      margin-left: auto;
      margin-right: auto;
    }}
    .line-legend-row {{
      display: grid;
      grid-template-columns: 12px 1fr auto;
      gap: 0.45rem;
      align-items: center;
    }}
    .line-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
    }}
    .bar-value {{ font-weight: 600; font-size: 0.9rem; color: var(--ink); min-width: 4ch; text-align: right; }}
    .latest-list {{
      max-height: 360px;
      overflow: auto;
      border: 1px solid #ece6da;
      border-radius: 10px;
      background: #fff;
    }}
    .split-lists {{
      margin-top: 0.2rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 0.8rem;
    }}
    .split-title {{
      font-size: 0.86rem;
      font-weight: 700;
      color: #36515d;
      margin: 0 0 0.35rem;
    }}
    .issue-desc {{
      display: block;
      margin-top: 0.15rem;
      font-size: 0.78rem;
      color: var(--muted);
      line-height: 1.3;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 0.55rem 0.8rem; border-bottom: 1px solid #ece6da; font-size: 0.94rem; }}
    th:last-child, td:last-child {{ text-align: right; }}
    tr:nth-child(even) td {{ background: #fffaf0; }}
    .clickable-row td {{ cursor: pointer; }}
    .clickable-row:hover td {{ background: #eef8f6 !important; }}
    .detail-area {{ margin-top: 1rem; }}
    .footer-note {{ margin-top: 1rem; color: var(--muted); font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="header">
      <h1>AI supported Siroforce Tickets Analysis IO Sensor systems</h1>
      <p id="meta" class="header-meta">Source: - | Generated at: -</p>

      <div class="toolbar" style="margin-top: 0.7rem;">
        <label for="regionSelect">Region Filter</label>
        <select id="regionSelect"></select>
        <span class="muted">US = Support Hub US, EU = known EU codes, REST = all others.</span>
      </div>

      <div class="toolbar" style="margin-top: 0.7rem;">
        <label for="monthsSelect">Time Period</label>
        <select id="monthsSelect">
          <option value="ALL">Overall</option>
          <option value="1" selected>Last 1 month</option>
          <option value="2">Last 2 months</option>
          <option value="3">Last 3 months</option>
          <option value="6">Last 6 months</option>
          <option value="12">Last 12 months</option>
        </select>
        <span class="time-range-label" id="monthsRangeText"></span>
      </div>

      <div class="toolbar" style="margin-top: 0.7rem;">
        <label for="cat2Select">Category Level 2</label>
        <select id="cat2Select"></select>
        <span class="toolbar-break" aria-hidden="true"></span>
        <label for="firmwareSelect">Firmware Version</label>
        <select id="firmwareSelect"></select>
      </div>

      <div class="toolbar" style="margin-top: 0.7rem;">
        <span style="font-weight: 600;">Record Type Filter (Multi-select)</span>
        <label><input type="checkbox" class="rt-filter" value="COMPLAINT" checked> Complaint</label>
        <label><input type="checkbox" class="rt-filter" value="INQUIRY"> Inquiry</label>
        <label><input type="checkbox" class="rt-filter" value="REST" checked> Rest</label>
      </div>
    </section>

    <section class="cards">
      <article class="card">
        <div class="muted">Total Tickets</div>
        <div class="kpi" id="ticketsKpi">-</div>
      </article>
      <article class="card">
        <div class="muted">Active Region</div>
        <div class="kpi" id="regionKpi">-</div>
      </article>
      <article class="card">
        <div class="muted">Record Type Filter</div>
        <div class="kpi" id="recordTypeKpi">-</div>
      </article>
      <article class="card">
        <div class="muted">Time Period</div>
        <div class="kpi" id="monthsKpi">-</div>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <h3>Description Analysis</h3>
        <div class="panel-body">
          <div id="descPrimaryChart" class="bar-chart"></div>
          <div class="pie-wrap">
            <div class="muted" id="descPrimaryPieBase">Base: 0 tickets</div>
            <div class="pie-canvas-holder">
              <canvas id="descPrimaryPie" class="pie-canvas" width="300" height="300"></canvas>
              <svg id="descPrimaryPieCallouts" class="pie-callout-layer" aria-hidden="true"></svg>
              <div id="descPrimaryPieNotes" class="pie-notes-layer"></div>
            </div>
            <div class="pie-note-toolbar">
              <button id="addPieNoteBtn" type="button" class="pie-note-btn">Add text field</button>
              <button id="clearPieNotesBtn" type="button" class="pie-note-btn">Reset text fields</button>
            </div>
            <div id="descPrimaryPieLegend" class="pie-legend"></div>
          </div>
        </div>
      </article>

      <article class="panel">
        <h3>Description Analysis - Detail</h3>
        <div class="panel-body">
          <div class="chart-toolbar">
            <label for="descPrimaryFilterCopy">Description Category</label>
            <select id="descPrimaryFilterCopy"></select>
            <span class="toolbar-break" aria-hidden="true"></span>
            <label for="descSecondaryFilterCopy">Subcategory</label>
            <select id="descSecondaryFilterCopy"></select>
            <span class="toolbar-break" aria-hidden="true"></span>
            <label for="descSearchInput">Ticket Search</label>
            <input id="descSearchInput" type="text" placeholder="Search in ticket descriptionsâ€¦" style="padding:0.25rem 0.5rem;border:1px solid #ccc;border-radius:4px;font-size:0.85rem;min-width:200px;" />
            <span class="toolbar-break" aria-hidden="true"></span>
            <span class="muted" id="descMetaCopy"></span>
          </div>
          <div id="descPrimaryChartCopy" class="bar-chart"></div>
          <div class="latest-list" style="margin-top: 0.8rem;">
            <table>
              <thead><tr><th>Top Description</th><th>Tickets</th></tr></thead>
              <tbody id="descTopBodyCopy"></tbody>
            </table>
          </div>
        </div>
      </article>

      <div style="display:flex;flex-direction:column;gap:1rem;">
        <article class="panel">
          <h3>Spare Parts/RMA - Exchange Statistics</h3>
          <div class="panel-body">
            <div class="muted" id="sparePartMeta">Base: Tickets with Description Primary = Spare Parts/RMA/Logistics</div>
            <div id="sparePartChart" class="bar-chart" style="margin-top: 0.7rem;"></div>
            <div class="latest-list" style="margin-top: 0.8rem;">
              <table>
                <thead><tr><th>Subgroup</th><th>Count</th><th>Share</th></tr></thead>
                <tbody id="sparePartBody"></tbody>
              </table>
            </div>
          </div>
        </article>

        <article class="panel" id="clarityPanel" style="display:none;flex:1;">
          <h3>Ticket Clarity</h3>
          <div class="panel-body">
            <div class="muted" id="clarityMeta">Base: Tickets with Notes (CSV source only)</div>
            <div style="margin-top:0.8rem;">
              <table>
                <thead><tr><th>Category</th><th>Count</th><th>Share</th></tr></thead>
                <tbody id="clarityTableBody"></tbody>
              </table>
            </div>
            <div style="margin-top:1rem;">
              <div style="font-weight:700;color:#36515d;margin-bottom:0.35rem;">Top Resolved Solution Paths</div>
              <div class="muted" id="claritySolutionMeta">Base: Clear tickets with a documented solution</div>
              <div id="claritySolutionChart" class="bar-chart" style="margin-top: 0.7rem;"></div>
            </div>
          </div>
        </article>
      </div>

    </section>

    <section class="detail-area">
      <div style="display:flex;gap:1rem;align-items:stretch;height:520px;">
        <article class="panel" style="flex:2;min-width:0;display:flex;flex-direction:column;">
          <h3 id="descDetailTitle">Description Detail</h3>
          <div class="panel-body" style="flex:1;display:flex;flex-direction:column;">
            <div id="descDetailHint" class="muted">Select a Top Description row to see transactions.</div>
            <div style="margin-top:0.6rem;display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">
              <label for="descDetailTransactionFilter">Transaction Number</label>
              <input id="descDetailTransactionFilter" type="text" placeholder="Filter transaction number..." style="padding:0.25rem 0.5rem;border:1px solid #ccc;border-radius:4px;font-size:0.85rem;min-width:220px;" />
            </div>
            <div class="latest-list" style="margin-top: 0.6rem;flex:1;overflow-y:auto;">
              <table>
                <thead><tr><th>Created At</th><th>Transaction Number</th><th>Category Level 3</th><th>Category Level 4</th><th>Desc. Category</th><th>Desc. Subcategory</th><th>Contact Person</th><th>Clarity</th><th>Region</th></tr></thead>
                <tbody id="descDetailBodyCopy"></tbody>
              </table>
            </div>
          </div>
        </article>
        <article class="panel" id="notesPanel" style="flex:1;min-width:0;display:none;flex-direction:column;">
          <h3>Ticket Notes</h3>
          <div class="panel-body" style="flex:1;display:flex;flex-direction:column;min-height:0;">
            <div id="notesTicketId" class="muted" style="margin-bottom:0.5rem;"></div>
            <pre id="notesContent" style="white-space:pre-wrap;word-break:break-word;font-size:0.8rem;flex:1;min-height:0;overflow-y:auto;background:#f9f9f9;padding:0.75rem;border-radius:4px;margin:0;"></pre>
          </div>
        </article>
      </div>
    </section>

    <section class="detail-area">
      <article class="panel">
        <h3>TOP 10 Major Issues - Software, Hardware and Imaging</h3>
        <div class="panel-body">
          <div class="split-lists">
            <div>
              <p class="split-title">TOP 10 Software Issues</p>
              <div class="latest-list">
                <table>
                  <thead><tr><th>Software Theme</th><th>Tickets</th></tr></thead>
                  <tbody id="softwareTop10Body"></tbody>
                </table>
              </div>
            </div>
            <div>
              <p class="split-title">TOP 10 Hardware Issues</p>
              <div class="latest-list">
                <table>
                  <thead><tr><th>Hardware Theme</th><th>Tickets</th></tr></thead>
                  <tbody id="hardwareTop10Body"></tbody>
                </table>
              </div>
            </div>
            <div>
              <p class="split-title">TOP 10 Imaging Issues</p>
              <div class="latest-list">
                <table>
                  <thead><tr><th>Imaging Theme</th><th>Tickets</th></tr></thead>
                  <tbody id="imagingTop10Body"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="detail-area">
      <article class="panel">
        <h3>Category Trend by Month</h3>
        <div class="panel-body">
          <div class="line-wrap">
            <div class="line-canvas-holder">
              <canvas id="descTrendLine" class="line-canvas" width="760" height="300"></canvas>
            </div>
            <div id="descTrendLegend" class="line-legend"></div>
          </div>
        </div>
      </article>
    </section>

    <p class="footer-note">Note: This HTML is static; filtering is applied client-side in the browser.</p>
  </div>

  <script>
    const data = {payload};

    const nf = new Intl.NumberFormat('de-DE');
    const PIE_NOTE_STORAGE_KEY = 'descPrimaryPieNotesV1';
    let pieNotes = [];
    let pieNoteIdCounter = 1;
    let pieNoteResizeObserver = null;
    let currentPieSlices = [];
    let currentDescriptionDetailRows = [];
    let currentSelectedDescription = '';
    let currentDescriptionDetailSourceRows = [];

    function esc(text) {{
      return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function fillTable(bodyId, rows) {{
      const body = document.getElementById(bodyId);
      body.innerHTML = rows.map(([name, value]) =>
        `<tr><td>${{esc(name)}}</td><td>${{nf.format(value)}}</td></tr>`
      ).join('');
    }}

    function sortRows(mapObj, maxRows = null) {{
      const list = Array.from(mapObj.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      return maxRows ? list.slice(0, maxRows) : list;
    }}

    function renderBars(targetId, ranked, emptyText) {{
      const chartEl = document.getElementById(targetId);
      if (!ranked.length) {{
        chartEl.innerHTML = `<div class=\"muted\">${{esc(emptyText)}}</div>`;
        return;
      }}

      const maxValue = ranked[0][1] || 1;
      chartEl.innerHTML = ranked.map(([name, value]) => {{
        const width = Math.max(2, Math.round((value / maxValue) * 100));
        return `
          <div class=\"bar-row\">
            <div class=\"bar-label\">${{esc(name)}}</div>
            <div class=\"bar-track\"><div class=\"bar-fill\" style=\"width:${{width}}%\"></div></div>
            <div class=\"bar-value\">${{nf.format(value)}}</div>
          </div>
        `;
      }}).join('');
    }}

    function preparePieRows(ranked, maxSlices = 8) {{
      if (!ranked.length) return [];
      const sliced = ranked.slice(0, maxSlices);
      const rest = ranked.slice(maxSlices);
      if (!rest.length) return sliced;
      if (rest.length === 1) return [...sliced, rest[0]];

      const restValue = rest.reduce((sum, [, value]) => sum + value, 0);
      return restValue > 0 ? [...sliced, ['Other', restValue]] : sliced;
    }}

    function renderPieChart(canvasId, legendId, ranked, emptyText) {{
      const canvas = document.getElementById(canvasId);
      const legendEl = document.getElementById(legendId);
      if (!canvas || !legendEl) return;

      const ctx = canvas.getContext('2d');
      const pieRows = preparePieRows(ranked, 8);
      if (!pieRows.length) {{
        currentPieSlices = [];
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        legendEl.innerHTML = `<div class=\"muted\">${{esc(emptyText)}}</div>`;
        renderPieCallouts();
        return;
      }}

      const palette = [
        '#0f766e', '#155e75', '#2f6f8f', '#3d8ba6',
        '#579fb8', '#72b2c7', '#90c4d4', '#b0d6e0', '#d2e8ec'
      ];

      const total = pieRows.reduce((sum, [, value]) => sum + value, 0) || 1;
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const radius = Math.min(canvas.width, canvas.height) * 0.45;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      let startAngle = -Math.PI / 2;
      currentPieSlices = [];
      pieRows.forEach(([, value], idx) => {{
        const angle = (value / total) * Math.PI * 2;
        const endAngle = startAngle + angle;

        currentPieSlices.push({{
          name: pieRows[idx][0],
          start: startAngle,
          end: endAngle,
        }});

        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, radius, startAngle, endAngle);
        ctx.closePath();
        ctx.fillStyle = palette[idx % palette.length];
        ctx.fill();

        startAngle = endAngle;
      }});

      legendEl.innerHTML = pieRows.map(([name, value], idx) => {{
        const percent = ((value / total) * 100).toFixed(1);
        return `
          <div class=\"pie-legend-row\">
            <span class=\"pie-dot\" style=\"background:${{palette[idx % palette.length]}}\"></span>
            <span class=\"pie-label\">${{esc(name)}}</span>
            <span class=\"pie-value\">${{percent}}%</span>
          </div>
        `;
      }}).join('');

      renderPieCallouts();
    }}

    function getCategoryForAngle(angle) {{
      if (!currentPieSlices.length) return 'Category';

      let probe = angle;
      const base = -Math.PI / 2;
      const full = Math.PI * 2;
      while (probe < base) probe += full;
      while (probe >= base + full) probe -= full;

      const found = currentPieSlices.find(slice => probe >= slice.start && probe < slice.end);
      return found ? String(found.name || 'Category') : 'Category';
    }}

    function getSelectedRecordTypeGroups() {{
      return Array.from(document.querySelectorAll('.rt-filter:checked')).map(el => el.value);
    }}

    function parseDateIso(isoDate) {{
      if (!isoDate) return null;
      const d = new Date(`${{isoDate}}T00:00:00`);
      return Number.isNaN(d.getTime()) ? null : d;
    }}

    function formatDateDe(date) {{
      if (!date) return '-';
      return new Intl.DateTimeFormat('de-DE').format(date);
    }}

    function getMaxDate(rows) {{
      let maxDate = null;
      for (const row of rows) {{
        const d = parseDateIso(row.CreatedAt);
        if (!d) continue;
        if (!maxDate || d > maxDate) maxDate = d;
      }}
      return maxDate;
    }}

    function getMinDate(rows) {{
      let minDate = null;
      for (const row of rows) {{
        const d = parseDateIso(row.CreatedAt);
        if (!d) continue;
        if (!minDate || d < minDate) minDate = d;
      }}
      return minDate;
    }}

    function getDateRangeText(rows) {{
      const oldestDate = getMinDate(rows);
      const newestDate = getMaxDate(rows);
      if (!oldestDate || !newestDate) return 'Overall';
      return `${{formatDateDe(oldestDate)}} â†’ ${{formatDateDe(newestDate)}}`;
    }}

    function addMonths(date, monthsDelta) {{
      const copy = new Date(date);
      copy.setMonth(copy.getMonth() + monthsDelta);
      return copy;
    }}

    function inMonthWindow(rowDate, anchorDate, months) {{
      if (!rowDate || !anchorDate) return false;
      const cutoff = addMonths(anchorDate, -months);
      return rowDate >= cutoff && rowDate <= anchorDate;
    }}

    function summarizeRows(rows) {{
      const byRecordType = new Map();
      const byCat3 = new Map();

      let rowCount = 0;
      let ticketSum = 0;

      function add(mapObj, key, value) {{
        const k = key && key.trim() ? key : 'Unknown';
        mapObj.set(k, (mapObj.get(k) || 0) + value);
      }}

      for (const row of rows) {{
        rowCount += 1;
        const tickets = Number(row.Tickets) || 0;
        ticketSum += tickets;

        add(byRecordType, row['Record Type'], tickets);
        add(byCat3, row['Category Level 3'], tickets);
      }}

      function toSortedRows(mapObj, maxRows = null) {{
        const list = Array.from(mapObj.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
        return maxRows ? list.slice(0, maxRows) : list;
      }}

      return {{
        rows: rowCount,
        tickets: ticketSum,
        record_types: toSortedRows(byRecordType),
        category_level_3: toSortedRows(byCat3, 15),
      }};
    }}

    function normalizeCategory(value) {{
      if (!value || !value.trim()) return 'Unknown';
      const normalized = value.trim().replace(/\\s+/g, ' ');
      if (normalized.toLowerCase() === 'no sensor info') return 'No sensor info';
      return normalized;
    }}

    function parseGermanDateTimeToTs(datePart, timePart) {{
      const m = String(datePart || '').match(/^(\d{{2}})\.(\d{{2}})\.(\d{{4}})$/);
      if (!m || !timePart) return null;
      const day = Number(m[1]);
      const month = Number(m[2]);
      const year = Number(m[3]);
      const t = String(timePart).match(/^(\d{{2}}):(\d{{2}}):(\d{{2}})$/);
      if (!t) return null;
      const hour = Number(t[1]);
      const minute = Number(t[2]);
      const second = Number(t[3]);
      const parsed = new Date(year, month - 1, day, hour, minute, second);
      const ts = parsed.getTime();
      return Number.isNaN(ts) ? null : ts;
    }}

    function extractLatestContactPerson(notesText) {{
      if (!notesText) return '-';

      const lines = String(notesText).split(/\\r?\\n/);
      let latestTs = -1;
      let latestName = '';
      const entryPattern = /(\d{{2}}\.\d{{2}}\.\d{{4}})\s+(\d{{2}}:\d{{2}}:\d{{2}})\s+(.+)$/;

      for (const line of lines) {{
        const trimmed = line.trim();
        if (!trimmed) continue;
        const m = trimmed.match(entryPattern);
        if (!m) continue;

        const ts = parseGermanDateTimeToTs(m[1], m[2]);
        if (ts === null) continue;

        const person = String(m[3] || '').trim();
        if (!person || /^[-_]/.test(person)) continue;

        if (ts > latestTs) {{
          latestTs = ts;
          latestName = person;
        }}
      }}

      return latestName || '-';
    }}

    function updateSelectOptions(selectId, rows, fieldName, allLabel) {{
      const selectEl = document.getElementById(selectId);
      const previous = selectEl.value || 'ALL';
      const values = new Map();
      for (const row of rows) {{
        const key = normalizeCategory(row[fieldName]);
        values.set(key, (values.get(key) || 0) + (Number(row.Tickets) || 0));
      }}
      const options = Array.from(values.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      selectEl.innerHTML = [
        `<option value="ALL">${{esc(allLabel)}}</option>`,
        ...options.map(([name]) => `<option value="${{esc(name)}}">${{esc(name)}}</option>`),
      ].join('');
      const hasPrevious = previous === 'ALL' || options.some(([name]) => name === previous);
      selectEl.value = hasPrevious ? previous : 'ALL';
    }}

    function getRowsAfterGlobalFilters(region, selectedRecordTypeGroups, monthsWindow, selectedCat2, selectedFirmware) {{
      const anchorDate = getMaxDate(data.rows);
      return data.rows.filter(row =>
        (region === 'ALL' || row.Region === region) &&
        selectedRecordTypeGroups.includes(row.RecordTypeGroup) &&
        (monthsWindow === 'ALL' || inMonthWindow(parseDateIso(row.CreatedAt), anchorDate, Number(monthsWindow))) &&
        (selectedCat2 === 'ALL' || normalizeCategory(row['Category Level 2']) === selectedCat2) &&
        (selectedFirmware === 'ALL' || normalizeCategory(row['Firmware Version']) === selectedFirmware)
      );
    }}

    function renderDescriptionAnalysis(allRows) {{
      const byBucket = new Map();
      for (const row of allRows) {{
        const key = normalizeCategory(row['Description Primary']);
        byBucket.set(key, (byBucket.get(key) || 0) + (Number(row.Tickets) || 0));
      }}
      const ranked = sortRows(byBucket);
      const totalTickets = ranked.reduce((sum, [, value]) => sum + value, 0);
      const baseEl = document.getElementById('descPrimaryPieBase');
      if (baseEl) baseEl.textContent = `Base: ${{nf.format(totalTickets)}} tickets`;
      renderBars('descPrimaryChart', ranked.slice(0, 12), 'No data for the current selection.');
      renderPieChart('descPrimaryPie', 'descPrimaryPieLegend', ranked, 'No data for the current selection.');
    }}

    function renderCategoryTrendByMonth(allRows) {{
      const canvas = document.getElementById('descTrendLine');
      const legendEl = document.getElementById('descTrendLegend');
      if (!canvas || !legendEl) return;

      // Responsive canvas sizing for wide layouts with crisp HiDPI rendering.
      const dpr = Math.max(1, window.devicePixelRatio || 1);
      const holder = canvas.parentElement;
      const availableWidth = Math.max(700, Math.min(1220, Math.floor(holder?.clientWidth || 760)));
      const cssWidth = availableWidth;
      const cssHeight = Math.max(320, Math.min(420, Math.round(cssWidth * 0.46)));

      canvas.style.width = `${{cssWidth}}px`;
      canvas.style.height = `${{cssHeight}}px`;
      canvas.width = Math.round(cssWidth * dpr);
      canvas.height = Math.round(cssHeight * dpr);

      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const drawW = cssWidth;
      const drawH = cssHeight;
      const byMonth = new Map();
      const categoryTotals = new Map();

      for (const row of allRows) {{
        const createdAt = row.CreatedAt || '';
        if (!createdAt || createdAt.length < 7) continue;
        const monthKey = createdAt.slice(0, 7);
        const category = normalizeCategory(row['Description Primary']);
        const tickets = Number(row.Tickets) || 0;

        if (!byMonth.has(monthKey)) byMonth.set(monthKey, new Map());
        const monthMap = byMonth.get(monthKey);
        monthMap.set(category, (monthMap.get(category) || 0) + tickets);
        categoryTotals.set(category, (categoryTotals.get(category) || 0) + tickets);
      }}

      const months = Array.from(byMonth.keys()).sort((a, b) => a.localeCompare(b));
      if (!months.length) {{
        ctx.clearRect(0, 0, drawW, drawH);
        legendEl.innerHTML = '<div class="muted">No data for the current selection.</div>';
        return;
      }}

      const topCategories = Array.from(categoryTotals.entries())
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 6);

      if (!topCategories.length) {{
        ctx.clearRect(0, 0, drawW, drawH);
        legendEl.innerHTML = '<div class="muted">No data for the current selection.</div>';
        return;
      }}

      const series = topCategories.map(([name, total]) => {{
        const values = months.map(month => (byMonth.get(month)?.get(name) || 0));
        return {{ name, total, values }};
      }});

      const palette = ['#0f766e', '#155e75', '#2f6f8f', '#3d8ba6', '#579fb8', '#72b2c7'];
      const allValues = series.flatMap(s => s.values);
      const yMax = Math.max(...allValues, 0);
      const maxY = yMax > 0 ? yMax : 1;

      ctx.clearRect(0, 0, drawW, drawH);

      const padLeft = 54;
      const padRight = 20;
      const padTop = 18;
      const padBottom = 42;
      const plotW = drawW - padLeft - padRight;
      const plotH = drawH - padTop - padBottom;

      // Grid + y-axis labels
      ctx.strokeStyle = '#e5ded1';
      ctx.fillStyle = '#6b7780';
      ctx.lineWidth = 1;
      ctx.font = '12px Segoe UI';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      const gridLines = 4;
      for (let i = 0; i <= gridLines; i += 1) {{
        const ratio = i / gridLines;
        const y = padTop + plotH - ratio * plotH;
        const value = Math.round(ratio * maxY);

        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(padLeft + plotW, y);
        ctx.stroke();
        ctx.fillText(nf.format(value), padLeft - 6, y);
      }}

      // Axes
      ctx.strokeStyle = '#b9b0a2';
      ctx.beginPath();
      ctx.moveTo(padLeft, padTop);
      ctx.lineTo(padLeft, padTop + plotH);
      ctx.lineTo(padLeft + plotW, padTop + plotH);
      ctx.stroke();

      const stepX = months.length > 1 ? plotW / (months.length - 1) : 0;
      const monthLabelEvery = months.length > 10 ? Math.ceil(months.length / 10) : 1;

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#6b7780';
      months.forEach((month, idx) => {{
        if (idx % monthLabelEvery !== 0 && idx !== months.length - 1) return;
        const x = padLeft + stepX * idx;
        ctx.fillText(month, x, padTop + plotH + 8);
      }});

      series.forEach((line, lineIdx) => {{
        const color = palette[lineIdx % palette.length];
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 2;

        line.values.forEach((value, idx) => {{
          const x = months.length > 1 ? padLeft + stepX * idx : padLeft + plotW / 2;
          const y = padTop + plotH - (value / maxY) * plotH;
          if (idx === 0) {{
            ctx.beginPath();
            ctx.moveTo(x, y);
          }} else {{
            ctx.lineTo(x, y);
          }}
        }});
        ctx.stroke();

        line.values.forEach((value, idx) => {{
          const x = months.length > 1 ? padLeft + stepX * idx : padLeft + plotW / 2;
          const y = padTop + plotH - (value / maxY) * plotH;
          ctx.beginPath();
          ctx.arc(x, y, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }});
      }});

      legendEl.innerHTML = series.map((line, idx) => `
        <div class="line-legend-row">
          <span class="line-dot" style="background:${{palette[idx % palette.length]}}"></span>
          <span>${{esc(line.name)}}</span>
          <span class="pie-value">${{nf.format(line.total)}}</span>
        </div>
      `).join('');
    }}

    function renderSparePartStats(allRows) {{
      const spareRows = allRows.filter(row => normalizeCategory(row['Description Primary']) === 'Spare Parts/RMA/Logistics');
      const chartEl = document.getElementById('sparePartChart');
      const bodyEl = document.getElementById('sparePartBody');
      const metaEl = document.getElementById('sparePartMeta');
      if (!chartEl || !bodyEl || !metaEl) return;

      const totals = new Map([
        ['Sensor', 0],
        ['Remote', 0],
        ['Sensor Cable', 0],
        ['USB Cable', 0],
        ['Unassigned', 0],
      ]);

      for (const row of spareRows) {{
        const tickets = Number(row.Tickets) || 0;
        const group = row.SparePartGroup || 'Unassigned';
        totals.set(group, (totals.get(group) || 0) + tickets);
      }}

      const totalTickets = Array.from(totals.values()).reduce((a, b) => a + b, 0);
      const ranked = Array.from(totals.entries())
        .filter(([, value]) => value > 0)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));

      metaEl.textContent = `Base: ${{nf.format(totalTickets)}} tickets`;

      renderBars('sparePartChart', ranked, 'No Spare Parts/RMA tickets in the current selection.');

      if (!ranked.length) {{
        bodyEl.innerHTML = '<tr><td colspan="3" class="muted">No Spare Parts/RMA tickets in the current selection.</td></tr>';
        return;
      }}

      bodyEl.innerHTML = ranked.map(([name, value]) => {{
        const share = totalTickets > 0 ? ((value / totalTickets) * 100).toFixed(1) : '0.0';
        return `<tr><td>${{esc(name)}}</td><td>${{nf.format(value)}}</td><td>${{share}}%</td></tr>`;
      }}).join('');
    }}

    function renderClarityStats(allRows) {{
      const panel = document.getElementById('clarityPanel');
      const body = document.getElementById('clarityTableBody');
      const meta = document.getElementById('clarityMeta');
      const solutionMeta = document.getElementById('claritySolutionMeta');
      if (!body) return;
      const withNotes = allRows.filter(row => row.Notes);
      const clear = withNotes.filter(row => row.Clarity === 'clear').length;
      const unclear = withNotes.filter(row => row.Clarity === 'unclear').length;
      const total = withNotes.length;
      if (!total) {{
        if (panel) panel.style.display = 'none';
        return;
      }}
      if (panel) panel.style.display = '';
      if (meta) meta.textContent = `Base: ${{nf.format(total)}} tickets with Notes`;
      const rows = [
        ['âœ“ Ticket with clearness', clear],
        ['âœ— Ticket without clearness', unclear],
      ];
      body.innerHTML = rows.map(([name, value]) => {{
        const share = ((value / total) * 100).toFixed(1);
        const color = name.startsWith('âœ“') ? 'color:#2e7d32;font-weight:600;' : 'color:#c62828;font-weight:600;';
        return `<tr><td style="${{color}}">${{esc(name)}}</td><td>${{nf.format(value)}}</td><td>${{share}}%</td></tr>`;
      }}).join('');

      const solutionCounts = new Map();
      const clearRows = withNotes.filter(row => row.Clarity === 'clear');
      let solutionBase = 0;
      for (const row of clearRows) {{
        const solutionPath = row.SolutionPath || 'Other resolved action';
        const tickets = Number(row.Tickets) || 0;
        solutionBase += tickets;
        solutionCounts.set(solutionPath, (solutionCounts.get(solutionPath) || 0) + tickets);
      }}

      const solutionRanked = sortRows(solutionCounts, 8);
      if (solutionMeta) solutionMeta.textContent = `Base: ${{nf.format(solutionBase)}} clear tickets with Notes`;
      renderBars('claritySolutionChart', solutionRanked, 'No clear tickets with a documented solution in the current selection.');
    }}

    function loadPieNotes() {{
      try {{
        const raw = localStorage.getItem(PIE_NOTE_STORAGE_KEY);
        if (!raw) {{
          pieNotes = [];
          return;
        }}
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {{
          pieNotes = [];
          return;
        }}
        pieNotes = parsed
          .filter(item => item && typeof item === 'object')
          .map(item => ({{
            id: Number(item.id) || Date.now(),
            x: Math.min(95, Math.max(0, Number(item.x) || 0)),
            y: Math.min(95, Math.max(0, Number(item.y) || 0)),
            w: Math.min(220, Math.max(120, Number(item.w) || 170)),
            h: Math.min(200, Math.max(68, Number(item.h) || 92)),
            anchorAngle: Number.isFinite(Number(item.anchorAngle)) ? Number(item.anchorAngle) : null,
            text: String(item.text || ''),
          }}));
        pieNoteIdCounter = pieNotes.reduce((maxId, item) => Math.max(maxId, item.id), 0) + 1;
      }} catch {{
        pieNotes = [];
      }}
    }}

    function savePieNotes() {{
      localStorage.setItem(PIE_NOTE_STORAGE_KEY, JSON.stringify(pieNotes));
    }}

    function updatePieNote(id, fields) {{
      const note = pieNotes.find(item => item.id === id);
      if (!note) return;
      Object.assign(note, fields);
      savePieNotes();
    }}

    function removePieNote(id) {{
      pieNotes = pieNotes.filter(item => item.id !== id);
      savePieNotes();
      renderPieNotes();
    }}

    function addPieNote() {{
      pieNotes.push({{
        id: pieNoteIdCounter,
        x: 6,
        y: 6,
        w: 170,
        h: 92,
        anchorAngle: null,
        text: 'Edit text',
      }});
      pieNoteIdCounter += 1;
      savePieNotes();
      renderPieNotes();
    }}

    function clearPieNotes() {{
      pieNotes = [];
      savePieNotes();
      renderPieNotes();
    }}

    function renderPieNotes() {{
      const layer = document.getElementById('descPrimaryPieNotes');
      if (!layer) return;

      layer.innerHTML = '';
      pieNotes.forEach(note => {{
        const box = document.createElement('div');
        box.className = 'pie-note';
        box.dataset.noteId = String(note.id);
        box.style.left = `${{note.x}}%`;
        box.style.top = `${{note.y}}%`;
        box.style.width = `${{note.w}}px`;
        box.style.height = `${{note.h}}px`;

        const head = document.createElement('div');
        head.className = 'pie-note-head';
        head.innerHTML = '<span class="pie-note-category">Category</span>';

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'pie-note-delete';
        delBtn.textContent = 'x';
        delBtn.title = 'Delete';
        delBtn.addEventListener('click', (event) => {{
          event.stopPropagation();
          removePieNote(note.id);
        }});
        head.appendChild(delBtn);

        const text = document.createElement('div');
        text.className = 'pie-note-text';
        text.contentEditable = 'true';
        text.textContent = note.text;
        text.addEventListener('input', () => {{
          updatePieNote(note.id, {{ text: text.textContent || '' }});
        }});

        box.appendChild(head);
        box.appendChild(text);
        layer.appendChild(box);

        head.addEventListener('mousedown', (event) => {{
          event.preventDefault();
          const startX = event.clientX;
          const startY = event.clientY;
          const startNoteX = note.x;
          const startNoteY = note.y;

          const onMove = (moveEvent) => {{
            const rect = layer.getBoundingClientRect();
            if (!rect.width || !rect.height) return;

            const dxPct = ((moveEvent.clientX - startX) / rect.width) * 100;
            const dyPct = ((moveEvent.clientY - startY) / rect.height) * 100;

            const nextX = Math.min(96, Math.max(0, startNoteX + dxPct));
            const nextY = Math.min(96, Math.max(0, startNoteY + dyPct));
            box.style.left = `${{nextX}}%`;
            box.style.top = `${{nextY}}%`;
            updatePieNote(note.id, {{ x: nextX, y: nextY }});
            renderPieCallouts();
          }};

          const onUp = () => {{
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
          }};

          document.addEventListener('mousemove', onMove);
          document.addEventListener('mouseup', onUp);
        }});
      }});

      if (pieNoteResizeObserver) {{
        pieNoteResizeObserver.disconnect();
        layer.querySelectorAll('.pie-note').forEach(el => pieNoteResizeObserver.observe(el));
      }}

      renderPieCallouts();
    }}

    function renderPieCallouts() {{
      const svg = document.getElementById('descPrimaryPieCallouts');
      const layer = document.getElementById('descPrimaryPieNotes');
      const canvas = document.getElementById('descPrimaryPie');
      if (!svg || !layer || !canvas) return;

      const layerRect = layer.getBoundingClientRect();
      const canvasRect = canvas.getBoundingClientRect();
      if (!layerRect.width || !layerRect.height || !canvasRect.width || !canvasRect.height) {{
        svg.innerHTML = '';
        return;
      }}

      svg.setAttribute('viewBox', `0 0 ${{layerRect.width}} ${{layerRect.height}}`);
      svg.innerHTML = '';

      const cx = (canvasRect.left - layerRect.left) + canvasRect.width / 2;
      const cy = (canvasRect.top - layerRect.top) + canvasRect.height / 2;
      const radius = Math.min(canvasRect.width, canvasRect.height) * 0.45;
      const notesById = new Map(pieNotes.map(note => [note.id, note]));

      layer.querySelectorAll('.pie-note').forEach(noteEl => {{
        const noteId = Number(noteEl.dataset.noteId || 0);
        const note = notesById.get(noteId);
        if (!note) return;

        const noteRect = noteEl.getBoundingClientRect();
        const nx = (noteRect.left - layerRect.left) + noteRect.width / 2;
        const ny = (noteRect.top - layerRect.top) + noteRect.height / 2;

        const autoAngle = Math.atan2(ny - cy, nx - cx);
        const lineAngle = Number.isFinite(note.anchorAngle) ? note.anchorAngle : autoAngle;
        const px = cx + Math.cos(lineAngle) * radius;
        const py = cy + Math.sin(lineAngle) * radius;

        const categoryEl = noteEl.querySelector('.pie-note-category');
        if (categoryEl) {{
          const categoryName = getCategoryForAngle(lineAngle);
          categoryEl.textContent = categoryName;
        }}

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', String(px));
        line.setAttribute('y1', String(py));
        line.setAttribute('x2', String(nx));
        line.setAttribute('y2', String(ny));
        line.setAttribute('class', 'pie-callout-line');
        svg.appendChild(line);

        const handle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        handle.setAttribute('cx', String(px));
        handle.setAttribute('cy', String(py));
        handle.setAttribute('r', '5');
        handle.setAttribute('class', 'pie-callout-handle');
        handle.addEventListener('mousedown', (event) => {{
          event.preventDefault();
          event.stopPropagation();

          const onMove = (moveEvent) => {{
            const angle = Math.atan2(moveEvent.clientY - canvasRect.top - canvasRect.height / 2, moveEvent.clientX - canvasRect.left - canvasRect.width / 2);
            updatePieNote(note.id, {{ anchorAngle: angle }});
            renderPieCallouts();
          }};

          const onUp = () => {{
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
          }};

          document.addEventListener('mousemove', onMove);
          document.addEventListener('mouseup', onUp);
        }});
        svg.appendChild(handle);
      }});
    }}

    function initPieNotes() {{
      if (typeof ResizeObserver !== 'undefined') {{
        pieNoteResizeObserver = new ResizeObserver(entries => {{
          entries.forEach(entry => {{
            const el = entry.target;
            const noteId = Number(el.dataset.noteId || 0);
            if (!noteId) return;

            const nextW = Math.min(220, Math.max(120, Math.round(el.offsetWidth)));
            const nextH = Math.min(200, Math.max(68, Math.round(el.offsetHeight)));
            updatePieNote(noteId, {{ w: nextW, h: nextH }});
          }});
          renderPieCallouts();
        }});
      }}

      loadPieNotes();
      renderPieNotes();

      const addBtn = document.getElementById('addPieNoteBtn');
      const clearBtn = document.getElementById('clearPieNotesBtn');
      if (addBtn) addBtn.addEventListener('click', addPieNote);
      if (clearBtn) clearBtn.addEventListener('click', clearPieNotes);
      window.addEventListener('resize', renderPieCallouts);
    }}

    function renderDescriptionAnalysisCopy(allRows, selectedPrimary, selectedSecondary) {{
      const metaEl = document.getElementById('descMetaCopy');
      const rowsAfterDesc = allRows.filter(row =>
        (selectedPrimary === 'ALL' || normalizeCategory(row['Description Primary']) === selectedPrimary) &&
        (selectedSecondary === 'ALL' || normalizeCategory(row['Description Secondary']) === selectedSecondary)
      );
      currentDescriptionDetailSourceRows = rowsAfterDesc;
      currentDescriptionDetailRows = [];
      currentSelectedDescription = '';
      renderCurrentDescriptionDetailRows();

      const byBucket = new Map();
      const bucketField = selectedPrimary === 'ALL' ? 'Description Primary' : 'Description Secondary';
      for (const row of rowsAfterDesc) {{
        const key = normalizeCategory(row[bucketField]);
        byBucket.set(key, (byBucket.get(key) || 0) + (Number(row.Tickets) || 0));
      }}
      renderBars('descPrimaryChartCopy', sortRows(byBucket, 12), 'No data for the current selection.');

      const byDescription = new Map();
      const searchTerm = (document.getElementById('descSearchInput')?.value || '').toLowerCase().trim();
      const rowsForTopDesc = searchTerm
        ? rowsAfterDesc.filter(row => (row['Description'] || '').toLowerCase().includes(searchTerm))
        : rowsAfterDesc;
      for (const row of rowsForTopDesc) {{
        const key = normalizeCategory(row['Description']);
        byDescription.set(key, (byDescription.get(key) || 0) + (Number(row.Tickets) || 0));
      }}

      const topDescriptions = sortRows(byDescription, 20);
      const descBody = document.getElementById('descTopBodyCopy');
      if (!topDescriptions.length) {{
        descBody.innerHTML = '<tr><td colspan="2" class="muted">No data for the current selection.</td></tr>';
        currentDescriptionDetailRows = [];
        currentSelectedDescription = '';
        renderCurrentDescriptionDetailRows();
      }} else {{
        descBody.innerHTML = topDescriptions.map(([name, value]) =>
          `<tr class="clickable-row" data-description="${{esc(name)}}"><td>${{esc(name)}}</td><td>${{nf.format(value)}}</td></tr>`
        ).join('');

        descBody.querySelectorAll('tr.clickable-row').forEach(rowEl => {{
          rowEl.addEventListener('click', () => {{
            const selectedDescription = rowEl.getAttribute('data-description') || '';
            const txFilter = document.getElementById('descDetailTransactionFilter');
            if (txFilter) txFilter.value = '';
            renderDescriptionDetailInline(rowsForTopDesc, selectedDescription);
          }});
        }});
      }}

      const primaryLabel = selectedPrimary === 'ALL' ? 'All categories' : selectedPrimary;
      const secondaryLabel = selectedSecondary === 'ALL' ? 'All subcategories' : selectedSecondary;
      metaEl.textContent = `Active: ${{primaryLabel}} + ${{secondaryLabel}}`;
    }}

    function renderCurrentDescriptionDetailRows() {{
      const titleEl = document.getElementById('descDetailTitle');
      const hintEl = document.getElementById('descDetailHint');
      const bodyEl = document.getElementById('descDetailBodyCopy');
      const transactionFilterEl = document.getElementById('descDetailTransactionFilter');
      if (!titleEl || !hintEl || !bodyEl || !transactionFilterEl) return;

      function toDetailRows(rows) {{
        return rows
          .map(row => ({{
            createdAt: row.CreatedAt || '-',
            transaction: row['Transaction Number'] || '-',
            category3: row['Category Level 3'] || '-',
            category4: row['Category Level 4'] || '-',
            descPrimary: row['Description Primary'] || '-',
            descSecondary: row['Description Secondary'] || '-',
            contactPerson: extractLatestContactPerson(row.Notes || ''),
            region: row.Region || '-',
            notes: row.Notes || '',
            clarity: row.Clarity || '',
            ts: parseDateIso(row.CreatedAt)?.getTime() || 0,
          }}))
          .sort((a, b) => b.ts - a.ts || String(b.transaction).localeCompare(String(a.transaction)));
      }}

      const filterValue = String(transactionFilterEl.value || '').trim().toLowerCase();

      if (filterValue) {{
        const visibleRows = toDetailRows(
          data.rows.filter(row => String(row['Transaction Number'] || '').toLowerCase().includes(filterValue))
        );
        titleEl.textContent = 'Transaction Search Result';
        hintEl.innerHTML = `Transaction Number: <strong>${{esc(transactionFilterEl.value.trim())}}</strong> | Rows: ${{nf.format(visibleRows.length)}}`;
        bodyEl.innerHTML = visibleRows.length
          ? visibleRows.map(item => item.notes
              ? `<tr style="cursor:pointer;" onclick="showNotes('${{esc(item.transaction)}}', this)" data-notes="${{esc(item.notes)}}"><td>${{esc(item.createdAt)}}</td><td>${{esc(item.transaction)}}</td><td>${{esc(item.category3)}}</td><td>${{esc(item.category4)}}</td><td>${{esc(item.descPrimary)}}</td><td>${{esc(item.descSecondary)}}</td><td>${{esc(item.contactPerson)}}</td><td style="text-align:center;font-size:1rem;">${{item.clarity === 'clear' ? 'âœ“' : item.clarity === 'unclear' ? 'âœ—' : ''}}</td><td>${{esc(item.region)}}</td></tr>`
              : `<tr><td>${{esc(item.createdAt)}}</td><td>${{esc(item.transaction)}}</td><td>${{esc(item.category3)}}</td><td>${{esc(item.category4)}}</td><td>${{esc(item.descPrimary)}}</td><td>${{esc(item.descSecondary)}}</td><td>${{esc(item.contactPerson)}}</td><td></td><td>${{esc(item.region)}}</td></tr>`
            ).join('')
          : '<tr><td colspan="9" class="muted">No matching transactions found.</td></tr>';
        return;
      }}

      if (!currentSelectedDescription) {{
        titleEl.textContent = 'Tickets selected by Description';
        hintEl.textContent = 'Select a Top Description row or search for a transaction number.';
        bodyEl.innerHTML = '<tr><td colspan="9" class="muted">No description selected.</td></tr>';
        return;
      }}

      titleEl.textContent = 'Description Detail';
      hintEl.innerHTML = `Description: <strong>${{esc(currentSelectedDescription)}}</strong> | Rows: ${{nf.format(currentDescriptionDetailRows.length)}}`;
      bodyEl.innerHTML = currentDescriptionDetailRows.length
        ? currentDescriptionDetailRows.map(item => item.notes
            ? `<tr style="cursor:pointer;" onclick="showNotes('${{esc(item.transaction)}}', this)" data-notes="${{esc(item.notes)}}"><td>${{esc(item.createdAt)}}</td><td>${{esc(item.transaction)}}</td><td>${{esc(item.category3)}}</td><td>${{esc(item.category4)}}</td><td>${{esc(item.descPrimary)}}</td><td>${{esc(item.descSecondary)}}</td><td>${{esc(item.contactPerson)}}</td><td style="text-align:center;font-size:1rem;">${{item.clarity === 'clear' ? 'âœ“' : item.clarity === 'unclear' ? 'âœ—' : ''}}</td><td>${{esc(item.region)}}</td></tr>`
            : `<tr><td>${{esc(item.createdAt)}}</td><td>${{esc(item.transaction)}}</td><td>${{esc(item.category3)}}</td><td>${{esc(item.category4)}}</td><td>${{esc(item.descPrimary)}}</td><td>${{esc(item.descSecondary)}}</td><td>${{esc(item.contactPerson)}}</td><td></td><td>${{esc(item.region)}}</td></tr>`
          ).join('')
        : '<tr><td colspan="9" class="muted">No matching transactions found.</td></tr>';
    }}

    function renderDescriptionDetailInline(sourceRows, selectedDescription) {{
      if (!selectedDescription) {{
        currentSelectedDescription = '';
        currentDescriptionDetailRows = [];
        renderCurrentDescriptionDetailRows();
        return;
      }}

      currentSelectedDescription = selectedDescription;
      currentDescriptionDetailSourceRows = sourceRows;
      currentDescriptionDetailRows = sourceRows
        .filter(row => normalizeCategory(row['Description']) === selectedDescription)
        .map(row => ({{
          createdAt: row.CreatedAt || '-',
          transaction: row['Transaction Number'] || '-',
          category3: row['Category Level 3'] || '-',
          category4: row['Category Level 4'] || '-',
          descPrimary: row['Description Primary'] || '-',
          descSecondary: row['Description Secondary'] || '-',
          contactPerson: extractLatestContactPerson(row.Notes || ''),
          region: row.Region || '-',
          notes: row.Notes || '',
          clarity: row.Clarity || '',
          ts: parseDateIso(row.CreatedAt)?.getTime() || 0,
        }}))
        .sort((a, b) => b.ts - a.ts || String(b.transaction).localeCompare(String(a.transaction)));
      renderCurrentDescriptionDetailRows();
    }}

    const softwareThemeDescriptions = {{
      'IOSS Performance / Slowness': 'Reduced IOSS performance with delayed workflow response times.',
      'SIDEXIS Issue': 'SIDEXIS-related functional or stability incident affecting operations.',
      'Integration Issue (Curve/CDR/Patterson)': 'Interface or interoperability issue with third-party practice management software.',
      'Update/Upgrade Failure': 'Regression observed after software update, upgrade, or environment migration.',
      'Driver Problem': 'Driver or TWAIN layer malfunction impacting device communication.',
      'Crash/Freeze/Hang': 'Application becomes unresponsive, freezes, or terminates unexpectedly.',
      'Database/ODBC/SQL Error': 'Database connectivity or query execution fault within SQL/ODBC components.',
      'Service Start/Runtime Issue': 'Supporting service fails to start or remain stable during runtime.',
      'Template/Configuration Issue': 'Invalid or inconsistent configuration/template state affecting functionality.',
      'Version/Plugin Mismatch': 'Compatibility mismatch between application version and plugin/module.',
      'General Software Problem (Unspecified)': 'Software incident reported without sufficient detail for precise classification.',
    }};

    const hardwareThemeDescriptions = {{
      'Sensor Not Detected (Persistent)': 'Sensor remains consistently undetected and cannot be initialized.',
      'Sensor Connection Intermittent': 'Sensor connectivity is unstable with repeated drop-and-recover behavior.',
      'Remote/Interface Not Detected': 'Remote/interface is not recognized by the host environment.',
      'Remote/Interface No Power or No Function': 'Remote/interface shows no power state or no functional response.',
      'USB/Port/Communication Issue': 'Communication failure on USB/port path between components.',
      'Cable Fault / Loose Contact': 'Cable integrity or contact stability issue causing unreliable operation.',
      'Physical Device Damage': 'Physical damage condition impacting hardware reliability or function.',
      'Remote/Interface Intermittent Dropouts': 'Remote/interface connection drops intermittently during active use.',
      'Sensor Defect / Failure': 'Confirmed sensor hardware malfunction with persistent failure symptoms.',
      'General Hardware/Recognition Problem (Unspecified)': 'Hardware recognition incident without enough detail for deeper diagnosis.',
    }};

    const imagingThemeDescriptions = {{
      'Cannot Acquire Image - No Capture': 'Image capture cannot be initiated or completed successfully.',
      'Image Quality - Blurry/Artifact/Lines': 'Image output quality is degraded by blur, artifacts, or line noise.',
      'White/Black Image Output': 'Image output is saturated or blank (white/black), preventing diagnosis.',
      'Exposure Trigger Issue': 'Exposure trigger sequence behaves incorrectly or inconsistently.',
      'Slow Image Acquisition/Transfer': 'Acquisition and/or transfer latency delays clinical workflow.',
      'Duplicate/Wrong Image Display': 'Incorrect or duplicate image is displayed relative to expected case.',
      'Sensor Ready-State Imaging Issue': 'Sensor fails to enter or maintain imaging-ready state.',
      'Intermittent Image Drop/Acquire': 'Image stream is intermittently lost or acquisition fails sporadically.',
      'Calibration/Template Related Imaging Issue': 'Calibration/template control failure interrupts imaging availability.',
      'General Imaging Issue (Unspecified)': 'Imaging incident reported without sufficient detail for finer grouping.',
    }};

    function getThemeDescription(theme, descriptionMap) {{
      return descriptionMap[theme] || 'Issue pattern identified from ticket notes.';
    }}

    function renderSoftwareHardwareTop10(rows) {{
      const softwareMap = new Map();
      const hardwareMap = new Map();
      const imagingMap = new Map();

      function classifyTop10MajorIssue(row) {{
        if (!row.MajorIssueDomain) return null;
        return {{ domain: row.MajorIssueDomain, theme: row.MajorIssueTheme }};
      }}

      function add(mapObj, key, value) {{
        if (!key) return;
        mapObj.set(key, (mapObj.get(key) || 0) + value);
      }}

      for (const row of rows) {{
        const tickets = Number(row.Tickets) || 0;
        const majorIssue = classifyTop10MajorIssue(row);
        if (!majorIssue) continue;
        if (majorIssue.domain === 'software') add(softwareMap, majorIssue.theme, tickets);
        if (majorIssue.domain === 'hardware') add(hardwareMap, majorIssue.theme, tickets);
        if (majorIssue.domain === 'imaging') add(imagingMap, majorIssue.theme, tickets);
      }}

      const softwareTop = sortRows(softwareMap, 10);
      const hardwareTop = sortRows(hardwareMap, 10);
      const imagingTop = sortRows(imagingMap, 10);
      const softwareBody = document.getElementById('softwareTop10Body');
      const hardwareBody = document.getElementById('hardwareTop10Body');
      const imagingBody = document.getElementById('imagingTop10Body');

      if (softwareBody) {{
        softwareBody.innerHTML = softwareTop.length
          ? softwareTop.map(([name, value]) => `<tr><td><div>${{esc(name)}}</div><span class="issue-desc">${{esc(getThemeDescription(name, softwareThemeDescriptions))}}</span></td><td>${{nf.format(value)}}</td></tr>`).join('')
          : '<tr><td colspan="2" class="muted">No software themes in the current selection.</td></tr>';
      }}

      if (hardwareBody) {{
        hardwareBody.innerHTML = hardwareTop.length
          ? hardwareTop.map(([name, value]) => `<tr><td><div>${{esc(name)}}</div><span class="issue-desc">${{esc(getThemeDescription(name, hardwareThemeDescriptions))}}</span></td><td>${{nf.format(value)}}</td></tr>`).join('')
          : '<tr><td colspan="2" class="muted">No hardware themes in the current selection.</td></tr>';
      }}

      if (imagingBody) {{
        imagingBody.innerHTML = imagingTop.length
          ? imagingTop.map(([name, value]) => `<tr><td><div>${{esc(name)}}</div><span class="issue-desc">${{esc(getThemeDescription(name, imagingThemeDescriptions))}}</span></td><td>${{nf.format(value)}}</td></tr>`).join('')
          : '<tr><td colspan="2" class="muted">No imaging themes in the current selection.</td></tr>';
      }}
    }}

    function showNotes(transactionId, rowEl) {{
      const notes = rowEl.getAttribute('data-notes') || '';
      const panel = document.getElementById('notesPanel');
      const content = document.getElementById('notesContent');
      const ticketIdEl = document.getElementById('notesTicketId');
      document.querySelectorAll('#descDetailBodyCopy tr').forEach(r => r.style.background = '');
      rowEl.style.background = '#d4e8f0';
      ticketIdEl.textContent = 'Ticket: ' + transactionId;
      content.textContent = notes;
      panel.style.display = 'flex';
    }}

    function render(region, selectedRecordTypeGroups, monthsWindow, selectedCat2, selectedFirmware) {{
      const monthsRangeEl = document.getElementById('monthsRangeText');

      const baseRows = getRowsAfterGlobalFilters(region, selectedRecordTypeGroups, monthsWindow, 'ALL', 'ALL');
      updateSelectOptions('cat2Select', baseRows, 'Category Level 2', 'All Category Level 2');
      updateSelectOptions('firmwareSelect', baseRows, 'Firmware Version', 'All Firmware Versions');

      const cat2Current = document.getElementById('cat2Select').value;
      const firmwareCurrent = document.getElementById('firmwareSelect').value;
      const filteredRows = getRowsAfterGlobalFilters(region, selectedRecordTypeGroups, monthsWindow, cat2Current, firmwareCurrent);
      const filteredRowsAllMonths = getRowsAfterGlobalFilters(region, selectedRecordTypeGroups, 'ALL', cat2Current, firmwareCurrent);

      if (monthsRangeEl) {{
        monthsRangeEl.textContent = monthsWindow === 'ALL'
          ? getDateRangeText(filteredRowsAllMonths)
          : getDateRangeText(filteredRows);
      }}

      updateSelectOptions('descPrimaryFilterCopy', filteredRows, 'Description Primary', 'All Description Categories');
      const selectedDescPrimaryCopy = document.getElementById('descPrimaryFilterCopy').value;
      const rowsAfterDescPrimaryCopy = selectedDescPrimaryCopy === 'ALL'
        ? filteredRows
        : filteredRows.filter(row => normalizeCategory(row['Description Primary']) === selectedDescPrimaryCopy);
      updateSelectOptions('descSecondaryFilterCopy', rowsAfterDescPrimaryCopy, 'Description Secondary', 'All Description Subcategories');
      const selectedDescSecondaryCopy = document.getElementById('descSecondaryFilterCopy').value;

      const s = summarizeRows(filteredRows);
      document.getElementById('ticketsKpi').textContent = nf.format(s.tickets);
      document.getElementById('regionKpi').textContent = region;
      document.getElementById('recordTypeKpi').textContent = selectedRecordTypeGroups.length
        ? selectedRecordTypeGroups.join(', ')
        : 'None';
      const monthsKpiEl = document.getElementById('monthsKpi');
      if (monthsWindow === 'ALL') {{
        const rangeText = getDateRangeText(filteredRowsAllMonths);
        monthsKpiEl.innerHTML = `Overall<div class="kpi-subline">${{esc(rangeText)}}</div>`;
      }} else {{
        monthsKpiEl.textContent = `${{monthsWindow}} month(s)`;
      }}

      renderDescriptionAnalysis(filteredRows);
      renderSparePartStats(filteredRows);
      renderClarityStats(filteredRows);
      renderSoftwareHardwareTop10(filteredRows);
      renderCategoryTrendByMonth(filteredRowsAllMonths);
      renderDescriptionAnalysisCopy(filteredRows, selectedDescPrimaryCopy, selectedDescSecondaryCopy);
    }}

    const select = document.getElementById('regionSelect');
    const monthsSelect = document.getElementById('monthsSelect');
    const cat2Select = document.getElementById('cat2Select');
    const firmwareSelect = document.getElementById('firmwareSelect');
    const descPrimaryFilterCopy = document.getElementById('descPrimaryFilterCopy');
    const descSecondaryFilterCopy = document.getElementById('descSecondaryFilterCopy');
    select.innerHTML = data.available_regions
      .map(region => `<option value="${{region}}">${{region}}</option>`)
      .join('');

    function renderFromUi() {{
      render(select.value, getSelectedRecordTypeGroups(), monthsSelect.value, cat2Select.value, firmwareSelect.value);
    }}

    select.addEventListener('change', renderFromUi);
    monthsSelect.addEventListener('change', renderFromUi);
    cat2Select.addEventListener('change', renderFromUi);
    firmwareSelect.addEventListener('change', renderFromUi);
    document.querySelectorAll('.rt-filter').forEach(el => el.addEventListener('change', renderFromUi));
    descPrimaryFilterCopy.addEventListener('change', renderFromUi);
    descSecondaryFilterCopy.addEventListener('change', renderFromUi);
    const descSearchInput = document.getElementById('descSearchInput');
    if (descSearchInput) descSearchInput.addEventListener('input', renderFromUi);
    const descDetailTransactionFilter = document.getElementById('descDetailTransactionFilter');
    if (descDetailTransactionFilter) descDetailTransactionFilter.addEventListener('input', renderCurrentDescriptionDetailRows);

    const generatedAt = esc(data.meta.generated_at);
    const sourceFile = esc(data.meta.source_file);
    document.getElementById('meta').innerHTML = `Source: <strong>${{sourceFile}}</strong> &nbsp;|&nbsp; Generated at: ${{generatedAt}}`;

    initPieNotes();
    renderFromUi();
  </script>
</body>
</html>
"""




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
        "Language": t.get("language", ""),
        "Notes": t.get("notes_text", ""),
        "Clarity": t.get("clarity", "unclear"),
        "SparePartGroup": t.get("spare_part_group", ""),
        "MajorIssueDomain": t.get("major_issue_domain", ""),
        "MajorIssueTheme": t.get("major_issue_theme", ""),
        "SolutionPath": t.get("solution_path", ""),
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
    parser = argparse.ArgumentParser(description="Stage 3: tickets_classified.json â†’ HTML-Report")
    parser.add_argument("--input", default="output/tickets_classified.json")
    parser.add_argument("--output", default="Ticket_Report_CSV.html")
    args = parser.parse_args()

    classified_path = Path(args.input)
    if not classified_path.exists():
        raise FileNotFoundError(f"Klassifizierte Daten nicht gefunden: {classified_path}  â†’  Erst Stage 2 ausfuehren.")

    render(classified_path, Path(args.output))


if __name__ == "__main__":
    main()

