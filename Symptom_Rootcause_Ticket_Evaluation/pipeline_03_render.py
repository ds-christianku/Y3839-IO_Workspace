#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_03_render.py
Renders symptom analysis as a self-contained HTML report with trend charts.
"""

import json
import base64
import html
import re
import getpass
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
INPUT_PATH = BASE_DIR / "output" / "symptom_analysis.json"
OUTPUT_PATH = BASE_DIR / "output" / "Symptom_Trend_Report.html"
CHARTJS_PATH = BASE_DIR / "output" / "chart.umd.min.js"


def _trend_icon(pct):
    if pct is None:
        return '<span class="trend-new">NEW</span>'
    if pct > 50:
        return f'<span class="trend-up-strong">▲▲ +{pct:.0f}%</span>'
    if pct > 10:
        return f'<span class="trend-up">▲ +{pct:.0f}%</span>'
    if pct > -10:
        return f'<span class="trend-stable">→ {pct:+.0f}%</span>'
    if pct > -50:
        return f'<span class="trend-down">▼ {pct:.0f}%</span>'
    return f'<span class="trend-down-strong">▼▼ {pct:.0f}%</span>'


def _bar(value, max_value, color="#2a7a9b"):
    pct = int(value / max_value * 100) if max_value else 0
    return f'<div class="bar-wrap"><div class="bar" style="width:{pct}%;background:{color}"></div><span class="bar-val">{value:,}</span></div>'


def _tag_rc(text):
    """Replace [HW], [SW], [FW], and [CM] with colored badges."""
    text = text.replace("[HW]", '<span style="background:#e67e22;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">HW</span>')
    text = text.replace("[SW]", '<span style="background:#2980b9;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">SW</span>')
    text = text.replace("[FW]", '<span style="background:#2980b9;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">SW</span>')
    text = text.replace("[CM]", '<span style="background:#16a34a;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">CM</span>')
    return text

def _normalize_status(status):
    """Map legacy values to the current display statuses."""
    if status == "Completed":
        return "Solved"
    return status or ""


def _rc_entry_status(entry, default=""):
  """Read status from either legacy string values or object entries."""
  if isinstance(entry, dict):
    return _normalize_status(entry.get("status", default))
  if entry is None:
    return _normalize_status(default)
  return _normalize_status(entry)


def _map_jira_ticket_status(status):
  """Normalize Jira ticket state into report status categories."""
  normalized = str(status or "").strip().upper()
  if normalized in {"ONHOLD"}:
    return "OnHold"
  if normalized in {"INANALYSIS"}:
    return "InAnalysis"
  if normalized in {"INPROGRESS"}:
    return "InProgress"
  if normalized in {"SOLVED"}:
    return "Solved"
  if normalized in {"IN PROGRESS", "IN QA"}:
    return "InProgress"
  if normalized in {"ACCEPTED"}:
    return "InAnalysis"
  if normalized in {"DONE", "RESOLVED", "CLOSED"}:
    return "Solved"
  if normalized:
    return "OnHold"
  return ""


def _collect_rc_statuses_for_counts(rc_entry, jira_tickets):
  """Return statuses to count for an RC; Jira RCs contribute one status per ticket."""
  statuses = []
  if jira_tickets:
    if isinstance(rc_entry, dict):
      stored_tickets = rc_entry.get("jira_tickets", [])
      if isinstance(stored_tickets, list) and stored_tickets:
        for ticket in stored_tickets:
          if not isinstance(ticket, dict):
            continue
          mapped = _map_jira_ticket_status(ticket.get("status") or ticket.get("jira_status"))
          if mapped:
            statuses.append(mapped)
        if statuses:
          return statuses
    for ticket in jira_tickets:
      mapped = _map_jira_ticket_status(ticket.get("status") if isinstance(ticket, dict) else "")
      if mapped:
        statuses.append(mapped)
    return statuses

  status = _rc_entry_status(rc_entry, "OnHold")
  return [status] if status else []


def _derive_status_from_tickets(ticket_entries):
  """Derive one aggregated status from Jira ticket statuses."""
  mapped = []
  if isinstance(ticket_entries, list):
    for ticket in ticket_entries:
      if not isinstance(ticket, dict):
        continue
      mapped_status = _map_jira_ticket_status(ticket.get("jira_status") or ticket.get("status"))
      if mapped_status:
        mapped.append(mapped_status)
  elif isinstance(ticket_entries, dict):
    for raw_status in ticket_entries.values():
      mapped_status = _map_jira_ticket_status(raw_status)
      if mapped_status:
        mapped.append(mapped_status)

  if not mapped:
    return ""
  if "InProgress" in mapped:
    return "InProgress"
  if "InAnalysis" in mapped:
    return "InAnalysis"
  if "OnHold" in mapped:
    return "OnHold"
  if "Solved" in mapped:
    return "Solved"
  return ""


def _history_rc_entry_status(entry):
  """Read status from history RC entries supporting both string and object formats."""
  if isinstance(entry, dict):
    explicit = _normalize_status(entry.get("status", ""))
    if explicit:
      return explicit
    return _derive_status_from_tickets(entry.get("jira_tickets", []))
  return _normalize_status(entry)


def _effective_status(status, tickets):
  """Hide RC status whenever Jira bugs are assigned to that RC."""
  normalized_status = _normalize_status(status)
  if tickets:
    return ""
  return normalized_status


def _normalize_rc_key(text):
  """Normalize root cause text for matching across data sources."""
  if not text:
    return ""
  cleaned = text.replace("(SW-solution)", "")
  cleaned = re.sub(r"\s*\[(HW|SW|FW|CM)\]\s*$", "", cleaned)
  cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
  return cleaned.lower()
  
def _lookup_rc_entry(rc_map, rc_name, default=None):
  """Get RC entry by exact key first, then by normalized key."""
  if not isinstance(rc_map, dict):
    return default
  if rc_name in rc_map:
    return rc_map[rc_name]
  target_key = _normalize_rc_key(rc_name)
  for stored_name, stored_value in rc_map.items():
    if _normalize_rc_key(stored_name) == target_key:
      return stored_value
  return default

def _status_select(symptom_name, rc, current_status):
  """Render an editable status dropdown for RCs without Jira bugs."""
  status_value = current_status if current_status in {"OnHold", "InAnalysis", "InProgress", "Solved"} else "OnHold"
  options = []
  for value, label in [
    ("OnHold", "OnHold"),
    ("InAnalysis", "InAnalysis"),
    ("InProgress", "InProgress"),
    ("Solved", "Solved"),
  ]:
    selected = " selected" if value == status_value else ""
    options.append(f'<option value="{value}"{selected}>{label}</option>')
  symptom_attr = html.escape(symptom_name, quote=True)
  rc_attr = html.escape(rc, quote=True)
  return (
    f'<select class="rc-status-select" data-symptom="{symptom_attr}" data-rc="{rc_attr}" '
    f'style="min-width:110px;border:1px solid #cbd5e1;border-radius:6px;padding:3px 8px;font-size:0.82em;background:white;color:#1f2937">'
    f'{"".join(options)}</select>'
  )


def _status_control_html(symptom_name, rc, status, tickets):
  """Render status badge or dropdown depending on Jira assignment and solve state."""
  effective_status = _effective_status(status, tickets)
  if tickets:
    return _status_badge("")
  if effective_status == "Solved":
    return _status_badge(effective_status)
  return _status_select(symptom_name, rc, effective_status)


def _release_selected_value(rc_entry, in_release_scope):
  """Resolve stored Yes/No release flag with fallback to solved_issues scope."""
  if isinstance(rc_entry, dict):
    raw_value = str(rc_entry.get("selected_for_release", "")).strip().lower()
    if raw_value in {"yes", "no"}:
      return "Yes" if raw_value == "yes" else "No"
  return "Yes" if in_release_scope else "No"


def _release_select(symptom_name, rc, selected_value):
  """Render Yes/No selector for release scope decision."""
  options = []
  normalized = "Yes" if str(selected_value).strip().lower() == "yes" else "No"
  for value in ["Yes", "No"]:
    selected = " selected" if value == normalized else ""
    options.append(f'<option value="{value}"{selected}>{value}</option>')
  symptom_attr = html.escape(symptom_name, quote=True)
  rc_attr = html.escape(rc, quote=True)
  return (
    f'<select class="rc-release-select" data-symptom="{symptom_attr}" data-rc="{rc_attr}" '
    f'style="min-width:70px;border:1px solid #cbd5e1;border-radius:6px;padding:3px 8px;font-size:0.82em;background:white;color:#1f2937">'
    f'{"".join(options)}</select>'
  )

def _status_badge(status):
    """Generate a colored status badge."""
    status = _normalize_status(status)
    if not status:
        return ""
    status_colors = {
        "OnHold": "#9ca3af",
        "InAnalysis": "#f59e0b",
        "InProgress": "#3b82f6",
        "Solved": "#10b981"
    }
    color = status_colors.get(status, "#9ca3af")
    return f'<span style="background:{color};color:white;border-radius:3px;padding:2px 6px;font-size:0.75em;font-weight:600;margin-left:8px;white-space:nowrap">{status}</span>'


def _backlog_item_html(item):
    title = item.get("title", "")
    description = item.get("description", "")
    url_match = re.search(r'https?://[^\s<>"\']+', description or "")
    url = url_match.group(0) if url_match else ""

    if url:
        title_html = (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#0055cc;text-decoration:underline;font-weight:700">{html.escape(title)}</a>'
        )
        escaped_desc = html.escape(description)
        escaped_url = html.escape(url)
        desc_html = f'<br><span style="font-size:0.82em;color:#555">{escaped_desc}</span>'
        desc_html = desc_html.replace(
            escaped_url,
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="color:#0055cc;text-decoration:underline">{escaped_url}</a>'
        )
    else:
        title_html = f'<strong>{html.escape(title)}</strong>'
        desc_html = f'<br><span style="font-size:0.82em;color:#555">{html.escape(description)}</span>' if description else ""
    return title_html + desc_html


def run():
    print("=== Pipeline 03: Render ===")

    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    symptoms = data["symptoms"]
    meta = data["meta"]
    years = meta["years"]
    total = meta["total_tickets"]
    generated = meta["generated_at"]

    date_min = meta.get("date_min", "")[:10]
    date_max = meta.get("date_max", "")[:10]
    date_range = f"{date_min} – {date_max}" if date_min and date_max else " / ".join(years)
    symptoms = sorted(data["symptoms"], key=lambda s: (s.get("priority", 99), -s["total"]))

    # Group by priority
    prio_labels = {1: "Priority 1", 2: "Priority 2", 3: "Priority 3", 4: "Priority 4"}
    prio_colors = {1: "#c0392b", 2: "#e67e22", 3: "#2980b9", 4: "#7f8c8d"}
    groups = {}
    for s in symptoms:
        prio = s.get("priority", 4)
        label = prio_labels.get(prio, f"Priority {prio}")
        groups.setdefault(label, []).append(s)

    max_total = max((s["total"] for s in symptoms), default=1)

    # Year-on-year columns
    y_headers = "".join(f"<th>{y}</th>" for y in years)
    if len(years) >= 2:
        y1, y2 = years[-2], years[-1]
    else:
        y1 = y2 = years[0] if years else ""

    # Build symptom rows
    def symptom_rows(sym_list):
        rows = ""
        for s in sym_list:
            kw = ", ".join(f"<code>{k}</code>" for k in s["keywords"])
            year_cells = "".join(f'<td class="num">{s["by_year"].get(y, 0):,}</td>' for y in years)
            trend = _trend_icon(s["trend_pct"])
            bar = _bar(s["total"], max_total)
            ai_cat = s.get("ai_category", "")
            ai_html = f'<span style="background:#e8f4f8;border:1px solid #b0d4e3;border-radius:4px;padding:2px 8px;font-size:0.82em;font-weight:500;white-space:nowrap">{ai_cat}</span>' if ai_cat else ""
            rc_list = s.get("root_causes", [])
            rc_html = "".join(f'<div style="font-size:0.8em;color:#555;margin-top:2px">&#8226; {_tag_rc(rc)}</div>' for rc in rc_list)
            hint = s.get("hint", "")
            hint_escaped = hint.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            hint_html = f'<div style="font-size:0.8em;color:#e67e22;margin-top:4px;font-style:italic">Hint: {hint_escaped}</div>' if hint else ""
            rows += f"""
      <tr>
        <td class="symptom-name">{s["name"]}<br>{rc_html}{hint_html}</td>
        <td>{bar}</td>
        <td class="num">{s["pct_of_total"]}%</td>
        {year_cells}
        <td class="trend-cell">{trend}</td>
        <td>{ai_html}</td>
        <td class="kw-cell">{kw}</td>
      </tr>"""
        return rows

    # Group sections
    sections = ""
    for group_name, sym_list in groups.items():
        group_total = sum(s["total"] for s in sym_list)
        prio_num = sym_list[0].get("priority", 4)
        color = prio_colors.get(prio_num, "#444")
        sections += f"""
    <section>
      <h2 style="border-left:6px solid {color};padding-left:12px;color:{color}">{group_name}
        <span class="group-total">{group_total:,} tickets</span>
      </h2>
      <table>
        <thead>
          <tr>
            <th>Symptom / Root Causes</th>
            <th>Ticket Volume</th>
            <th>% Total</th>
            {y_headers}
            <th>Trend {y1}→{y2}</th>
            <th>AI Categories (Top 3)</th>
            <th>Search Keywords</th>
          </tr>
        </thead>
        <tbody>{symptom_rows(sym_list)}</tbody>
      </table>
    </section>"""

    # Summary table sorted by priority then total desc
    sorted_symptoms = sorted(symptoms, key=lambda s: (s.get("priority", 99), -s["total"]))
    summary_rows = ""
    for s in sorted_symptoms:
        trend = _trend_icon(s["trend_pct"])
        c1 = s["by_year"].get(y1, 0)
        c2 = s["by_year"].get(y2, 0)
        prio_num = s.get("priority", 4)
        prio_col = prio_colors.get(prio_num, "#444")
        prio_label = prio_labels.get(prio_num, f"P{prio_num}")
        rc_list = s.get("root_causes", [])
        rc_summary = "  \u2022  ".join(rc_list)
        kw_tooltip = "\\n".join(s.get("keywords", []))
        year_cells_summary = "".join(
            f'<td class="num dyn-yr-{j}">{s["by_year"].get(y, 0):,}</td>'
            for j, y in enumerate(years)
        )
        ai_cat = s.get('ai_category', '')
        ai_cats = [c.strip() for c in ai_cat.split(',') if c.strip()]
        cat_badges = ''.join(
            f'<span style="background:#e8f4f8;border:1px solid #b0d4e3;border-radius:4px;padding:2px 7px;font-size:0.82em;font-weight:500;white-space:nowrap;margin-right:3px">{c}</span>'
            for c in ai_cats
        )
        summary_rows += f"""
        <tr data-prio="{prio_num}" data-cat="{ai_cat.replace('"','"')}">
          <td><span style="background:{prio_col};color:white;border-radius:4px;padding:2px 8px;font-size:0.82em;font-weight:600">{prio_label}</span></td>
          <td><span data-kw="{kw_tooltip}">{s["name"]}</span></td>
          <td>{cat_badges or '<span style="color:#aaa">-</span>'}</td>
          <td class="num dyn-total">{s["total"]:,}</td>
          <td class="num dyn-pct">{s["pct_of_total"]}%</td>
          {year_cells_summary}
          <td class="trend-cell dyn-trend">{trend}</td>
        </tr>"""

    # Embed market symptom overview image as base64
    img_b64 = ""
    img_path = BASE_DIR / "Screenshot 2026-08-24 102415.png"
    if img_path.exists():
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

    # Embed Chart.js inline for offline use
    chartjs_inline = ""
    if CHARTJS_PATH.exists():
        chartjs_inline = CHARTJS_PATH.read_text(encoding="utf-8")

    img_section = ""
    if img_b64:
        img_section = f"""
  <section style="margin-bottom:28px">
    <h2 style="font-size:1.1em;margin-bottom:12px;color:var(--accent)">Market Symptom Overview</h2>
    <img src="data:image/png;base64,{img_b64}" alt="Symptom descriptions from markets"
         style="max-width:100%;border-radius:6px;border:1px solid var(--border)" />
  </section>"""

    tickets_per_year = meta.get("tickets_per_year", {})
    year_breakdown = "  |  ".join(f"{y}: {c:,}" for y, c in tickets_per_year.items())
    market_md_path = BASE_DIR.parent / "Siroforce_Evaluation" / "market" / "market_symptom_analysis.json"
    # Use symptom_analysis.json grouped by original market groups for reference table
    MARKET_GROUPS = [
        ("Connectivity / Sensor Recognition", ["Intermittent Connectivity", "Images not transferred", "Loosening Screws"]),
        ("Power / Module Failure", ['"Dying Boxes" (USB module)', "No Power"]),
        ("Image Quality", ["White Images", "Overexposed images", "Previous (Patient) Image"]),
        ("Software / Update", ["Interface Update Issues", "Inconstant ready-for-exposure signaling (SW vs. Interface)", "3rd Party Slowness (NAM)"]),
    ]
    sym_by_name = {s["name"]: s for s in symptoms}
    market_ref_sections = ""
    for grp_name, names in MARKET_GROUPS:
        grp_rows = ""
        grp_total = 0
        for name in names:
            s = sym_by_name.get(name)
            if not s:
                continue
            grp_total += s["total"]
            kw = ", ".join(f"<code>{k}</code>" for k in s["keywords"])
            year_cells = "".join(f'<td class="num">{s["by_year"].get(y, 0):,}</td>' for y in years)
            grp_rows += f"""
            <tr>
              <td class="symptom-name">{s["name"]}</td>
              <td class="num">{s["total"]:,}</td>
              <td class="num">{s["pct_of_total"]}%</td>
              {year_cells}
              <td class="kw-cell">{kw}</td>
            </tr>"""
        market_ref_sections += f"""
        <tr style="background:#f0f4f8;font-weight:600">
          <td colspan="{3 + len(years) + 1}">{grp_name} &mdash; {grp_total:,} tickets</td>
        </tr>{grp_rows}"""

    # Load Jira-enriched analysis if available, otherwise fall back to standard
    jira_path = BASE_DIR / "output" / "symptom_analysis_jira.json"
    jira_issues_path    = BASE_DIR / "output" / "jira_issues.json"
    jira_summaries_path = BASE_DIR / "output" / "jira_summaries.json"
    rc_status_path = BASE_DIR / "output" / "rc_status.json"
    solved_issues_path = BASE_DIR / "output" / "solved_issues.json"
    if jira_path.exists():
        with open(jira_path, encoding="utf-8") as f:
            jira_data = json.load(f)
        jira_sym_map = {s["name"]: s for s in jira_data.get("symptoms", [])}
    else:
        jira_data = {}
        jira_sym_map = {}

    # Load status mappings if available
    # New structure: rc_status[symptom][rc] = status
    rc_status_map = {}
    selected_for_release_map = {}
    if rc_status_path.exists():
        with open(rc_status_path, encoding="utf-8") as f:
            rc_status_data = json.load(f)
        rc_status_map = rc_status_data.get("rc_status", {})
        selected_for_release_map = rc_status_data.get("selected_for_release", {})

    # Load status history if available
    rc_status_history = []
    rc_status_history_path = BASE_DIR / "output" / "rc_status_history.json"
    if rc_status_history_path.exists():
        with open(rc_status_history_path, encoding="utf-8") as f:
            rc_history_data = json.load(f)
        rc_status_history = rc_history_data.get("tracking_history", [])

    # Load release scope root causes from solved_issues.json
    release_rc_keys = set()
    if solved_issues_path.exists():
      with open(solved_issues_path, encoding="utf-8") as f:
        solved_issues_data = json.load(f)
      for issue in solved_issues_data.get("solved_issues", []):
        fixed_rootcause = (issue.get("fixed_rootcause") or "").strip()
        if not fixed_rootcause or fixed_rootcause == "-":
          continue
        for rc_item in fixed_rootcause.split(","):
          normalized_key = _normalize_rc_key(rc_item)
          if normalized_key:
            release_rc_keys.add(normalized_key)

    # Compute Jira coverage stats
    jira_total_bugs = 0
    jira_desc_map: dict = {}
    if jira_issues_path.exists():
        with open(jira_issues_path, encoding="utf-8") as f:
            all_issues = json.load(f)
        RESOLVED = {"Resolved", "Closed", "Done", "Won't Fix", "Rejected", "In QA"}
        jira_total_bugs = sum(1 for i in all_issues
                              if i.get("issuetype") == "Bug"
                              and i.get("status", "") not in RESOLVED)
        jira_desc_map = {i['key']: (i.get('description') or '') for i in all_issues}
    jira_summaries = json.loads(jira_summaries_path.read_text(encoding="utf-8")) if jira_summaries_path.exists() else {}
    solutions_path = BASE_DIR / "output" / "symptom_solutions.json"
    solutions_map  = json.loads(solutions_path.read_text(encoding="utf-8")) if solutions_path.exists() else {}
    backlog_path   = BASE_DIR / "output" / "rnd_backlog.json"
    backlog_items  = json.loads(backlog_path.read_text(encoding="utf-8")) if backlog_path.exists() else []
    # Show when jira_issues.json was last updated (= last Jira import)
    jira_import_date = ""
    if jira_issues_path.exists():
        import os as _os
        jira_import_date = datetime.fromtimestamp(_os.path.getmtime(jira_issues_path)).strftime("%Y-%m-%d %H:%M")
    jira_assigned_keys: set = set()
    for sym in jira_data.get("symptoms", []):
        for rc in sym.get("root_causes_jira", []):
            for t in rc.get("jira_tickets", []):
                jira_assigned_keys.add(t["key"])
    jira_assigned  = len(jira_assigned_keys)
    jira_unassigned = jira_total_bugs - jira_assigned
    jira_pct = round(jira_assigned / jira_total_bugs * 100) if jira_total_bugs else 0

    # Build Intermittent Connectivity RC breakdown for release chart
    import re as _re
    ic_hw_labels, ic_hw_counts = [], []
    ic_sw_labels, ic_sw_counts = [], []
    ic_cm_labels, ic_cm_counts = [], []
    for sym in jira_data.get("symptoms", []):
        if sym["name"] == "Intermittent Connectivity":
            for rc in sym.get("root_causes_jira", []):
                count = len(rc.get("jira_tickets", []))
                if count == 0:
                    continue
                label = _re.sub(r"\s*\[(HW|SW|FW|CM)\]", "", rc["text"]).strip()
                if "[CM]" in rc["text"]:
                    ic_cm_labels.append(label)
                    ic_cm_counts.append(count)
                elif "[HW]" in rc["text"]:
                    ic_hw_labels.append(label)
                    ic_hw_counts.append(count)
                else:
                    ic_sw_labels.append(label)
                    ic_sw_counts.append(count)
    import json as _json_ic
    ic_hw_labels_js = _json_ic.dumps(ic_hw_labels)
    ic_hw_counts_js = _json_ic.dumps(ic_hw_counts)
    ic_sw_labels_js = _json_ic.dumps(ic_sw_labels)
    ic_sw_counts_js = _json_ic.dumps(ic_sw_counts)
    ic_cm_labels_js = _json_ic.dumps(ic_cm_labels)
    ic_cm_counts_js = _json_ic.dumps(ic_cm_counts)
    ic_hw_total = sum(ic_hw_counts)
    ic_sw_total = sum(ic_sw_counts)
    ic_cm_total = sum(ic_cm_counts)
    # Siroforce tickets for Intermittent Connectivity
    ic_siroforce = next((s["total"] for s in symptoms if s["name"] == "Intermittent Connectivity"), 0)
    # Top 3 root causes by ticket count
    ic_all_rc = sorted(
        [(l, c, t) for l, c, t in list(zip(ic_hw_labels, ic_hw_counts, ['HW']*len(ic_hw_labels))) + 
                                       list(zip(ic_sw_labels, ic_sw_counts, ['SW']*len(ic_sw_labels))) +
                                       list(zip(ic_cm_labels, ic_cm_counts, ['CM']*len(ic_cm_labels)))],
        key=lambda x: -x[1]
    )[:3]
    ic_top3_html = "".join(
        f'<li style="margin-bottom:4px"><span style="font-weight:600;color:{"#e67e22" if t == "HW" else "#2563eb" if t == "SW" else "#16a34a"}">{c} Tickets</span> &ndash; {l} <span style="background:{"#e67e22" if t == "HW" else "#2980b9" if t == "SW" else "#16a34a"};color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">{t}</span></li>'
        for l, c, t in ic_all_rc
    )

    # Symptoms and Root Causes section — with Jira ticket links per root cause
    rc_section_rows = ""
    editable_rc_count = 0
    for s in sorted_symptoms:
        prio_num = s.get("priority", 4)
        prio_col = prio_colors.get(prio_num, "#444")
        prio_label = prio_labels.get(prio_num, f"P{prio_num}")
        rc_list = s.get("root_causes", [])
        ai_cat = s.get("ai_category", "")
        ai_cats = [c.strip() for c in ai_cat.split(',') if c.strip()]
        ai_badge = ''.join(
            f'<span style="background:#e8f4f8;border:1px solid #b0d4e3;border-radius:4px;padding:1px 6px;font-size:0.8em;white-space:nowrap;margin-right:3px">{c}</span>'
            for c in ai_cats
        ) if ai_cats else ""
        jira_enriched = (jira_sym_map.get(s["name"]) or {}).get("root_causes_jira", [])
        jira_by_rc = {r["text"]: r.get("jira_tickets", []) for r in jira_enriched}
        rc_map_rows_html = ""
        for rc in rc_list:
            tickets = jira_by_rc.get(rc, [])
            rc_id = f"rc-{abs(hash(s['name'] + rc)) % 99999}"
            raw_rc_entry = _lookup_rc_entry(rc_status_map.get(s["name"], {}), rc, "OnHold")
            rc_status_value = _rc_entry_status(raw_rc_entry, "OnHold")
            rc_status = _effective_status(rc_status_value, tickets)
            stored_release_value = ""
            symptom_release_map = selected_for_release_map.get(s["name"], {}) if isinstance(selected_for_release_map, dict) else {}
            if isinstance(symptom_release_map, dict):
              stored_release_value = _lookup_rc_entry(symptom_release_map, rc, "")
            if str(stored_release_value).strip().lower() in {"yes", "no"}:
                release_selected = "Yes" if str(stored_release_value).strip().lower() == "yes" else "No"
            else:
                release_selected = _release_selected_value(raw_rc_entry, _normalize_rc_key(rc) in release_rc_keys)

            release_control = _release_select(s["name"], rc, release_selected)
            status_badge = _status_control_html(s["name"], rc, rc_status_value, tickets)
            if not tickets and rc_status != "Solved":
                editable_rc_count += 1
            if tickets:
                ticket_count = len(tickets)
                ticket_details = ""
                for t in tickets:
                    tk = t["key"]
                    t_tip = (jira_summaries.get(tk) or t["summary"])[:500].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
                    ticket_details += (
                        f'<tr style="background:#fffef0;cursor:pointer" onclick="showBugDetail(\'{tk}\')" title="{t_tip}">'
                        f'<td style="padding:4px 8px;white-space:nowrap">'
                        f'<a href="{t["url"]}" target="_blank" style="font-weight:600;color:#856404;text-decoration:none" onclick="event.stopPropagation()">{tk}</a>'
                        f'</td>'
                        f'<td style="padding:4px 8px;font-size:0.82em;color:#555">{t["summary"][:90]}</td>'
                        f'<td style="padding:4px 8px;white-space:nowrap;font-size:0.8em">'
                        f'<span style="background:#e2e8f0;border-radius:3px;padding:1px 5px">{t["status"]}</span></td>'
                        f'<td style="padding:4px 8px;font-size:0.8em;color:#888">{t["priority"]}</td>'
                        f'</tr>'
                    )
                jira_toggle = (
                    f'<span onclick="toggleJira(\'{rc_id}\')" '
                    f'style="margin-left:8px;cursor:pointer;background:#ffc107;color:#333;'
                    f'border-radius:3px;padding:1px 6px;font-size:0.75em;font-weight:600;'
                    f'user-select:none" title="Show/hide Jira tickets">'
                    f'Jira Bugs: {ticket_count}</span>'
                    f'<table id="{rc_id}" style="display:none;margin-top:4px;margin-left:16px;'
                    f'border:1px solid #ffc107;border-radius:4px;font-size:0.82em;width:calc(100% - 16px)">'
                    f'<thead><tr style="background:#fff3cd">'
                    f'<th style="padding:3px 8px;text-align:left">Key</th>'
                    f'<th style="padding:3px 8px;text-align:left">Summary</th>'
                    f'<th style="padding:3px 8px;text-align:left">Status</th>'
                    f'<th style="padding:3px 8px;text-align:left">Priority</th>'
                    f'</tr></thead><tbody>{ticket_details}</tbody></table>'
                )
            else:
                jira_toggle = ""
            rc_map_rows_html += (
                '<tr>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top">{_tag_rc(rc)}{jira_toggle}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top;width:140px">{release_control}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top;width:130px">{status_badge}</td>'
                '</tr>'
            )
        # Add hint if present
        hint = s.get("hint", "")
        hint_html = ""
        if hint:
            hint_html_escaped = hint.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            hint_html = f'<div style="margin-top:8px;font-size:0.82em;color:#92400e;font-style:italic">Hint: {hint_html_escaped}</div>'
        rc_section_rows += f"""
        <tr>
          <td><span style="background:{prio_col};color:white;border-radius:4px;padding:2px 8px;font-size:0.82em;font-weight:600">{prio_label}</span></td>
          <td><strong>{s["name"]}</strong><br>{ai_badge}</td>
          <td colspan="3" style="padding:6px 8px">
            <table style="width:100%;border-collapse:collapse;font-size:0.86em;color:#334155;background:#f8fafc;border:1px solid #dbe7f0;border-radius:6px;overflow:hidden">
              <thead>
                <tr style="background:#eef4f9;color:#475569">
                  <th style="text-align:left;padding:6px 8px;font-weight:600">Root Cause</th>
                  <th style="text-align:left;padding:6px 8px;font-weight:600;width:140px">Selected for Release</th>
                  <th style="text-align:left;padding:6px 8px;font-weight:600;width:130px">Status</th>
                </tr>
              </thead>
              <tbody>{rc_map_rows_html}</tbody>
            </table>
            {hint_html}
          </td>
        </tr>"""

    # Nicht zugeordnete offene Bugs als eigener Block
    import json as _json
    jira_bugs_for_js: dict = {}
    if jira_issues_path.exists():
        _prio_order = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3, "Lowest": 4}
        _unassigned_bugs = sorted(
            [i for i in all_issues
             if i.get("issuetype") == "Bug"
             and i.get("status", "") not in RESOLVED
             and i["key"] not in jira_assigned_keys],
            key=lambda x: (_prio_order.get(x.get("priority", "Medium"), 99), x["key"])
        )
        if _unassigned_bugs:
            _ua_rc_id = "rc-unassigned"
            _ua_rows = ""
            for _t in _unassigned_bugs:
                _tk = _t["key"]
                _t_tip = (jira_summaries.get(_tk) or _t.get("summary") or "")[:500].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
                _prio_col_map = {"Urgent": "#c0392b", "High": "#e67e22", "Medium": "#2980b9", "Low": "#7f8c8d", "Lowest": "#95a5a6"}
                _p_col = _prio_col_map.get(_t.get("priority", "Medium"), "#444")
                _ua_rows += (
                    f'<tr style="background:#fafafa;cursor:pointer" onclick="showBugDetail(\'{_tk}\')" title="{_t_tip}">'
                    f'<td style="padding:4px 8px;white-space:nowrap">'
                    f'<a href="{_t["url"]}" target="_blank" style="font-weight:600;color:#856404;text-decoration:none" onclick="event.stopPropagation()">{_tk}</a>'
                    f'</td>'
                    f'<td style="padding:4px 8px;font-size:0.82em;color:#555">{(_t.get("summary") or "")[:90]}</td>'
                    f'<td style="padding:4px 8px;white-space:nowrap;font-size:0.8em"><span style="background:#e2e8f0;border-radius:3px;padding:1px 5px">{_t["status"]}</span></td>'
                    f'<td style="padding:4px 8px;font-size:0.8em"><span style="background:{_p_col};color:white;border-radius:3px;padding:1px 5px">{_t.get("priority","")}</span></td>'
                    f'</tr>'
                )
                jira_bugs_for_js[_tk] = {
                    "summary": (_t.get("summary") or ""),
                    "status": _t.get("status", ""),
                    "priority": _t.get("priority", ""),
                    "url": _t.get("url", ""),
                    "desc": jira_desc_map.get(_tk, "")[:700].replace('\r\n', '\n').replace('\r', '\n'),
                    "ai_summary": jira_summaries.get(_tk, ""),
                }
            _ua_toggle = (
                f'<span onclick="toggleJira(\'{_ua_rc_id}\')" '
                f'style="margin-left:8px;cursor:pointer;background:#6c757d;color:white;'
                f'border-radius:3px;padding:1px 6px;font-size:0.75em;font-weight:600;user-select:none">'
                f'Jira Bugs: {len(_unassigned_bugs)}</span>'
                f'<table id="{_ua_rc_id}" style="display:none;margin-top:4px;border:1px solid #aaa;'
                f'border-radius:4px;font-size:0.82em;width:100%">'
                f'<thead><tr style="background:#e9ecef">'
                f'<th style="padding:3px 8px;text-align:left">Key</th>'
                f'<th style="padding:3px 8px;text-align:left">Summary</th>'
                f'<th style="padding:3px 8px;text-align:left">Status</th>'
                f'<th style="padding:3px 8px;text-align:left">Priority</th>'
                f'</tr></thead><tbody>{_ua_rows}</tbody></table>'
            )
            rc_section_rows += f"""
        <tr style="background:#f8f9fa">
          <td><span style="background:#6c757d;color:white;border-radius:4px;padding:2px 8px;font-size:0.82em;font-weight:600">–</span></td>
          <td><strong>Not Assigned</strong><br><span style="font-size:0.8em;color:#888">{len(_unassigned_bugs)} open bugs without symptom assignment</span></td>
          <td><ul style="margin:0;padding-left:16px;font-size:0.88em;color:#666"><li>{_ua_toggle}</li></ul></td>
          <td></td>
        </tr>"""
    for _sym in jira_data.get("symptoms", []):
        for _rc in _sym.get("root_causes_jira", []):
            for _t in _rc.get("jira_tickets", []):
                _k = _t["key"]
                _desc = jira_desc_map.get(_k, "")[:700].replace('\r\n', '\n').replace('\r', '\n')
                jira_bugs_for_js[_k] = {
                    "summary": _t["summary"],
                    "status": _t["status"],
                    "priority": _t["priority"],
                    "url": _t["url"],
                    "desc": _desc,
                    "ai_summary": jira_summaries.get(_k, ""),
                }
    jira_bugs_js = _json.dumps(jira_bugs_for_js, ensure_ascii=False)
    # Build ticket→symptom/RC index for search
    ticket_index: dict = {}
    for _sym in jira_data.get("symptoms", []):
        for _rc in _sym.get("root_causes_jira", []):
            for _t in _rc.get("jira_tickets", []):
                _k = _t["key"]
                ticket_index.setdefault(_k, []).append({
                    "symptom": _sym["name"],
                    "rc": _rc["text"],
                    "status": _t.get("status", ""),
                    "priority": _t.get("priority", ""),
                    "url": _t.get("url", ""),
                    "summary": _t.get("summary", ""),
                })
    # Also add unassigned bugs to the index
    for _k in jira_bugs_for_js:
        if _k not in ticket_index:
            _b = jira_bugs_for_js[_k]
            ticket_index[_k] = [{
                "symptom": "Not Assigned",
                "rc": "–",
                "status": _b.get("status", ""),
                "priority": _b.get("priority", ""),
                "url": _b.get("url", ""),
                "summary": _b.get("summary", ""),
            }]
    ticket_index_js = _json.dumps(ticket_index, ensure_ascii=False)
    rc_status_data_js = _json.dumps({"rc_status": rc_status_map, "selected_for_release": selected_for_release_map}, ensure_ascii=False)
    release_rc_keys_js = _json.dumps(sorted(release_rc_keys), ensure_ascii=False)
    rc_status_history_data_js = _json.dumps({"tracking_history": rc_status_history}, ensure_ascii=False)
    windows_user_js = _json.dumps(getpass.getuser(), ensure_ascii=False)
    jira_rc_flags: dict = {}
    jira_rc_statuses: dict = {}
    jira_rc_tickets: dict = {}
    for _sym in jira_data.get("symptoms", []):
      jira_rc_flags[_sym["name"]] = {
        _rc["text"]: bool(_rc.get("jira_tickets", []))
        for _rc in _sym.get("root_causes_jira", [])
      }
      jira_rc_statuses[_sym["name"]] = {
        _rc["text"]: [_ticket.get("status", "") for _ticket in _rc.get("jira_tickets", [])]
        for _rc in _sym.get("root_causes_jira", [])
      }
      jira_rc_tickets[_sym["name"]] = {
        _rc["text"]: [
          {
            "key": _ticket.get("key", ""),
            "status": _ticket.get("status", ""),
          }
          for _ticket in _rc.get("jira_tickets", [])
        ]
        for _rc in _sym.get("root_causes_jira", [])
      }
    jira_rc_flags_js = _json.dumps(jira_rc_flags, ensure_ascii=False)
    jira_rc_statuses_js = _json.dumps(jira_rc_statuses, ensure_ascii=False)
    jira_rc_tickets_js = _json.dumps(jira_rc_tickets, ensure_ascii=False)
    # Flatten multi-category strings for dropdown
    ai_categories = sorted({c.strip() for s in symptoms for c in s.get('ai_category','').split(',') if c.strip()})
    ai_options = "".join(f'<option value="{c}">{c}</option>' for c in ai_categories)
    total_breakdown_js = _json.dumps(meta.get("total_breakdown", {}), ensure_ascii=False)
    symptom_data_js = _json.dumps([{
        "name": s["name"],
        "priority": s.get("priority", 99),
        "ai_category": [c.strip() for c in s.get("ai_category", "").split(',') if c.strip()],
        "breakdown": s.get("breakdown", {}),
        "keywords": s.get("keywords", []),
    } for s in sorted_symptoms], ensure_ascii=False)

    mapped = sum(s["total"] for s in symptoms)

    # Build Status Tracker - Overall counts from current rc_status.json
    global_status_counts = {"OnHold": 0, "InAnalysis": 0, "InProgress": 0, "Solved": 0}
    for s in sorted_symptoms:
      rc_list = s.get("root_causes", [])
      jira_enriched = (jira_sym_map.get(s["name"]) or {}).get("root_causes_jira", [])
      jira_by_rc = {r["text"]: r.get("jira_tickets", []) for r in jira_enriched}
      for rc in rc_list:
        raw_rc_entry = _lookup_rc_entry(rc_status_map.get(s["name"], {}), rc, "OnHold")
        for rc_status in _collect_rc_statuses_for_counts(raw_rc_entry, jira_by_rc.get(rc, [])):
          if rc_status in global_status_counts:
            global_status_counts[rc_status] += 1
    
    global_status_summary = ""
    for st_name, color in [("OnHold", "#9ca3af"), ("InAnalysis", "#f59e0b"), ("InProgress", "#3b82f6"), ("Solved", "#10b981")]:
        count = global_status_counts.get(st_name, 0)
        pct = round(count / sum(global_status_counts.values()) * 100, 1) if sum(global_status_counts.values()) > 0 else 0
        global_status_summary += f'<div style="background:{color};color:white;border-radius:6px;padding:12px 16px;text-align:center"><div style="font-weight:600;font-size:1.2em">{count}</div><div style="font-size:0.8em;opacity:0.9">{st_name} ({pct}%)</div></div>'

    # Build Status Tracker - Upcoming Release counts from latest history snapshot
    latest_history_status_map = {}
    if rc_status_history:
      latest_history_entry = rc_status_history[-1] if isinstance(rc_status_history[-1], dict) else {}
      latest_history_status_map = latest_history_entry.get("rc_status", {}) if isinstance(latest_history_entry, dict) else {}

    release_status_counts = {"OnHold": 0, "InAnalysis": 0, "InProgress": 0, "Solved": 0}
    if isinstance(latest_history_status_map, dict):
      for _symptom_name, rcs_dict in latest_history_status_map.items():
        if not isinstance(rcs_dict, dict):
          continue
        for rc_name, status in rcs_dict.items():
          normalized_status = _history_rc_entry_status(status)
          if normalized_status in release_status_counts:
            release_status_counts[normalized_status] += 1

    release_status_summary = ""
    for st_name, color in [("OnHold", "#9ca3af"), ("InAnalysis", "#f59e0b"), ("InProgress", "#3b82f6"), ("Solved", "#10b981")]:
      count = release_status_counts.get(st_name, 0)
      pct = round(count / sum(release_status_counts.values()) * 100, 1) if sum(release_status_counts.values()) > 0 else 0
      release_status_summary += f'<div style="background:{color};color:white;border-radius:6px;padding:12px 16px;text-align:center"><div style="font-weight:600;font-size:1.2em">{count}</div><div style="font-size:0.8em;opacity:0.9">{st_name} ({pct}%)</div></div>'

    # Build Status Timeline from History
    rc_timeline_html = ""
    rc_timeline_chart_data = {"weeks": [], "OnHold": [], "InAnalysis": [], "InProgress": [], "Solved": []}
    
    if rc_status_history:
        # Build timeline visualization
        for idx, entry in enumerate(rc_status_history):
            week = entry.get("week", "")
            date = entry.get("date", "")
            statuses = entry.get("rc_status", {})
            
            # Count statuses for this week (handle hierarchical structure: symptom -> rc -> status)
            week_counts = {"OnHold": 0, "InAnalysis": 0, "InProgress": 0, "Solved": 0}
            for symptom, rcs_dict in statuses.items():
              if isinstance(rcs_dict, dict):
                for rc_name, status in rcs_dict.items():
                  normalized_status = _history_rc_entry_status(status)
                  if normalized_status:
                    week_counts[normalized_status] = week_counts.get(normalized_status, 0) + 1
            
            rc_timeline_chart_data["weeks"].append(week)
            rc_timeline_chart_data["OnHold"].append(week_counts.get("OnHold", 0))
            rc_timeline_chart_data["InAnalysis"].append(week_counts.get("InAnalysis", 0))
            rc_timeline_chart_data["InProgress"].append(week_counts.get("InProgress", 0))
            rc_timeline_chart_data["Solved"].append(week_counts.get("Solved", 0))
            
            # Build timeline card HTML
            is_current = idx == len(rc_status_history) - 1
            card_style = "background:#f0f7ff;border:2px solid #3b82f6" if is_current else "background:#f8f9fa;border:1px solid #dde3ea"
            badge_current = '<span style="background:#3b82f6;color:white;border-radius:3px;padding:2px 6px;font-size:0.7em;font-weight:600;margin-left:8px">CURRENT</span>' if is_current else ""
            
            rc_timeline_html += f"""
        <div style="flex:1;min-width:200px;{card_style};border-radius:6px;padding:12px 14px;margin-bottom:12px">
          <div style="font-weight:600;font-size:0.85em;color:var(--accent)">{week} — {date}{badge_current}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;font-size:0.75em">
            <div style="background:#10b981;color:white;border-radius:4px;padding:6px 8px;text-align:center"><div style="font-weight:600;font-size:1.1em">{week_counts.get('Solved', 0)}</div>Solved</div>
            <div style="background:#3b82f6;color:white;border-radius:4px;padding:6px 8px;text-align:center"><div style="font-weight:600;font-size:1.1em">{week_counts.get('InProgress', 0)}</div>In Progress</div>
            <div style="background:#f59e0b;color:white;border-radius:4px;padding:6px 8px;text-align:center"><div style="font-weight:600;font-size:1.1em">{week_counts.get('InAnalysis', 0)}</div>In Analysis</div>
            <div style="background:#9ca3af;color:white;border-radius:4px;padding:6px 8px;text-align:center"><div style="font-weight:600;font-size:1.1em">{week_counts.get('OnHold', 0)}</div>On Hold</div>
          </div>
        </div>"""
        
        rc_timeline_chart_js = f"""
    // Status Timeline Chart
    const ctx_timeline = document.getElementById('rc-timeline-chart');
    if (ctx_timeline) {{
      new Chart(ctx_timeline, {{
        type: 'line',
        data: {{
          labels: {json.dumps(rc_timeline_chart_data["weeks"])},
          datasets: [
            {{
              label: 'Solved',
              data: {json.dumps(rc_timeline_chart_data["Solved"])},
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderWidth: 2.5,
              fill: true,
              tension: 0.3,
              pointRadius: 5,
              pointBackgroundColor: '#10b981'
            }},
            {{
              label: 'In Progress',
              data: {json.dumps(rc_timeline_chart_data["InProgress"])},
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.05)',
              borderWidth: 2.5,
              fill: true,
              tension: 0.3,
              pointRadius: 5,
              pointBackgroundColor: '#3b82f6'
            }},
            {{
              label: 'In Analysis',
              data: {json.dumps(rc_timeline_chart_data["InAnalysis"])},
              borderColor: '#f59e0b',
              backgroundColor: 'rgba(245, 158, 11, 0.05)',
              borderWidth: 2.5,
              fill: true,
              tension: 0.3,
              pointRadius: 5,
              pointBackgroundColor: '#f59e0b'
            }},
            {{
              label: 'On Hold',
              data: {json.dumps(rc_timeline_chart_data["OnHold"])},
              borderColor: '#9ca3af',
              backgroundColor: 'rgba(156, 163, 175, 0.05)',
              borderWidth: 2.5,
              fill: true,
              tension: 0.3,
              pointRadius: 5,
              pointBackgroundColor: '#9ca3af'
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: true,
          plugins: {{
            legend: {{
              display: true,
              position: 'top',
              labels: {{
                font: {{ size: 11, weight: '600' }},
                padding: 12,
                usePointStyle: true
              }}
            }},
            filler: {{
              propagate: true
            }}
          }},
          scales: {{
            x: {{
              title: {{ display: true, text: 'Week', font: {{ weight: '600' }} }},
              grid: {{ color: 'rgba(0, 0, 0, 0.05)' }}
            }},
            y: {{
              title: {{ display: true, text: 'Count', font: {{ weight: '600' }} }},
              beginAtZero: true,
              max: Math.max(...{json.dumps([max(rc_timeline_chart_data[s]) if rc_timeline_chart_data[s] else 0 for s in ["OnHold", "InAnalysis", "InProgress", "Solved"]])}) + 2,
              grid: {{ color: 'rgba(0, 0, 0, 0.05)' }}
            }}
          }}
        }}
      }});
    }}
"""
    else:
        rc_timeline_html = '<div style="color:#888;font-style:italic;padding:16px">No historical data available yet. Weekly snapshots will appear here after running save_rc_status_snapshot.py.</div>'
        rc_timeline_chart_js = ""

    # Build Symptom Status data for overall chart from current rc_status.json
    symptom_cards_html = ""
    symptom_stats = []

    for symptom in sorted_symptoms:
        symptom_name = symptom.get("name", "")
        rc_list = symptom.get("root_causes", [])
        jira_enriched = (jira_sym_map.get(symptom_name) or {}).get("root_causes_jira", [])
        jira_by_rc = {r["text"]: r.get("jira_tickets", []) for r in jira_enriched}

        completed = 0
        inprogress = 0
        inanalysis = 0
        onhold = 0

        for rc in rc_list:
            raw_rc_entry = _lookup_rc_entry(rc_status_map.get(symptom_name, {}), rc, "OnHold")
            rc_statuses = _collect_rc_statuses_for_counts(raw_rc_entry, jira_by_rc.get(rc, []))
            for rc_status in rc_statuses:
                if rc_status == "Solved":
                    completed += 1
                elif rc_status == "InProgress":
                    inprogress += 1
                elif rc_status == "InAnalysis":
                    inanalysis += 1
                elif rc_status == "OnHold":
                    onhold += 1

        symptom_total = completed + inprogress + inanalysis + onhold
        open_count = inanalysis + inprogress + onhold

        symptom_stats.append({
            "name": symptom_name,
            "completed": completed,
            "inprogress": inprogress,
            "inanalysis": inanalysis,
            "onhold": onhold,
            "total": symptom_total,
            "open": open_count,
        })
    
    # Sort symptom cards by open issues
    symptom_stats.sort(key=lambda x: x['open'], reverse=True)
    
    # Rebuild cards in sorted order
    symptom_cards_html = ""
    for stat in symptom_stats:
        # Build status bar segments
        status_bar_html = '<div style="display:flex;height:24px;border-radius:4px;overflow:hidden;background:#f0f0f0">'
        stat_total = stat['total']
        
        for status_val, count, color in [('completed', stat['completed'], '#10b981'), 
                                          ('inprogress', stat['inprogress'], '#3b82f6'),
                                          ('inanalysis', stat['inanalysis'], '#f59e0b'),
                                          ('onhold', stat['onhold'], '#9ca3af')]:
            if count > 0:
                width = (count / stat_total * 100)
                status_bar_html += f'<div style="width:{width}%;background:{color};display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:600" title="{status_val}: {count}">{count}</div>'
        
        status_bar_html += '</div>'
        
        symptom_cards_html += f"""
    <div style="background:white;border:1px solid #d0dde8;border-radius:6px;padding:14px;margin-bottom:12px">
      <div style="font-weight:600;font-size:0.95em;color:#333;margin-bottom:10px">{stat['name']}</div>
      {status_bar_html}
      <div style="font-size:11px;color:#666;text-align:right;margin-top:8px">{stat['open']} open / {stat['total']} total</div>
    </div>"""

    # Build per-symptom chart data for both scopes (Overall and Upcoming Release)
    overall_chart_labels = [stat["name"] for stat in symptom_stats]
    overall_chart_solved = [stat["completed"] for stat in symptom_stats]
    overall_chart_inprogress = [stat["inprogress"] for stat in symptom_stats]
    overall_chart_inanalysis = [stat["inanalysis"] for stat in symptom_stats]
    overall_chart_onhold = [stat["onhold"] for stat in symptom_stats]

    # Upcoming release timeline data from history (always 20 ISO weeks)
    def _week_key_to_monday(week_key):
      m = re.match(r"^(\d{{4}})-W(\d{{2}})$", str(week_key or "").strip())
      if not m:
        return None
      year, week = int(m.group(1)), int(m.group(2))
      try:
        return datetime.fromisocalendar(year, week, 1)
      except ValueError:
        return None

    def _monday_to_week_key(dt_obj):
      iso = dt_obj.isocalendar()
      return f"{iso.year}-W{iso.week:02d}"

    release_history_by_week = {}
    for entry in rc_status_history:
      week_key = entry.get("week", "")
      week_monday = _week_key_to_monday(week_key)
      if week_monday is None:
        date_raw = str(entry.get("date", "") or "")
        if not date_raw:
          continue
        try:
          parsed = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        except ValueError:
          continue
        week_monday = datetime.fromisocalendar(parsed.isocalendar().year, parsed.isocalendar().week, 1)
        week_key = _monday_to_week_key(week_monday)

      statuses = entry.get("rc_status", {})
      rel_counts = {"OnHold": 0, "InAnalysis": 0, "InProgress": 0, "Solved": 0}
      for _symptom_name, rcs_dict in statuses.items():
        if not isinstance(rcs_dict, dict):
          continue
        for rc_name, status in rcs_dict.items():
          normalized_status = _history_rc_entry_status(status)
          if normalized_status in rel_counts:
            rel_counts[normalized_status] += 1

      release_history_by_week[week_key] = rel_counts

    valid_week_mondays = [
      _week_key_to_monday(k)
      for k in release_history_by_week.keys()
      if _week_key_to_monday(k) is not None
    ]
    if valid_week_mondays:
      anchor_monday = max(valid_week_mondays)
    else:
      now = datetime.now()
      anchor_monday = datetime.fromisocalendar(now.isocalendar().year, now.isocalendar().week, 1)

    release_time_labels = []
    release_time_solved = []
    release_time_inprogress = []
    release_time_inanalysis = []
    release_time_onhold = []
    start_monday = anchor_monday

    for i in range(20):
      week_monday = start_monday + timedelta(weeks=i)
      week_key = _monday_to_week_key(week_monday)
      week_counts = release_history_by_week.get(
        week_key,
        {"OnHold": 0, "InAnalysis": 0, "InProgress": 0, "Solved": 0},
      )
      release_time_labels.append(week_key)
      release_time_solved.append(week_counts["Solved"])
      release_time_inprogress.append(week_counts["InProgress"])
      release_time_inanalysis.append(week_counts["InAnalysis"])
      release_time_onhold.append(week_counts["OnHold"])

    rc_timeline_chart_js = f"""
  // Status Development by Symptom (scope-specific stacked bars)
  function createStatusBySymptomChart(canvasId, labels, solvedData, inProgressData, inAnalysisData, onHoldData) {{
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [
          {{
            label: 'OnHold',
            data: onHoldData,
            backgroundColor: '#9ca3af',
            borderColor: '#64748b',
            borderWidth: 1,
            stack: 'rc-status'
          }},
          {{
            label: 'InAnalysis',
            data: inAnalysisData,
            backgroundColor: '#f59e0b',
            borderColor: '#d97706',
            borderWidth: 1,
            stack: 'rc-status'
          }},
          {{
            label: 'InProgress',
            data: inProgressData,
            backgroundColor: '#3b82f6',
            borderColor: '#2563eb',
            borderWidth: 1,
            stack: 'rc-status'
          }},
          {{
            label: 'Solved',
            data: solvedData,
            backgroundColor: '#10b981',
            borderColor: '#0f9b6f',
            borderWidth: 1,
            stack: 'rc-status'
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {{
          legend: {{
            display: true,
            position: 'top',
            labels: {{
              font: {{ size: 11, weight: '600' }},
              padding: 12,
              usePointStyle: true
            }}
          }}
        }},
        scales: {{
          x: {{
            stacked: true,
            ticks: {{
              maxRotation: 50,
              minRotation: 30,
              autoSkip: false,
              font: {{ size: 10 }}
            }},
            grid: {{ display: false }}
          }},
          y: {{
            stacked: true,
            beginAtZero: true,
            title: {{ display: true, text: 'Root Cause Count', font: {{ weight: '600' }} }},
            grid: {{ color: 'rgba(0, 0, 0, 0.06)' }}
          }}
        }}
      }}
    }});
  }}

  function createReleaseOverTimeChart(canvasId, timeLabels, solvedData, inProgressData, inAnalysisData, onHoldData) {{
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    function weekToDate(weekKey) {{
      const m = String(weekKey || '').match(/^(\d{{4}})-W(\d{{2}})$/);
      if (!m) return null;
      const year = Number(m[1]);
      const week = Number(m[2]);
      const jan4 = new Date(Date.UTC(year, 0, 4));
      const jan4Day = jan4.getUTCDay() || 7;
      const mondayWeek1 = new Date(jan4);
      mondayWeek1.setUTCDate(jan4.getUTCDate() - jan4Day + 1);
      const dt = new Date(mondayWeek1);
      dt.setUTCDate(mondayWeek1.getUTCDate() + (week - 1) * 7);
      return dt;
    }}

    function dateToWeekKey(dt) {{
      const d = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate()));
      const dayNum = d.getUTCDay() || 7;
      d.setUTCDate(d.getUTCDate() + 4 - dayNum);
      const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
      return `${{d.getUTCFullYear()}}-W${{String(weekNo).padStart(2, '0')}}`;
    }}

    // Enforce exactly 20 weeks on time axis.
    const labels = Array.isArray(timeLabels) ? [...timeLabels] : [];
    const solved = Array.isArray(solvedData) ? [...solvedData] : [];
    const inProgress = Array.isArray(inProgressData) ? [...inProgressData] : [];
    const inAnalysis = Array.isArray(inAnalysisData) ? [...inAnalysisData] : [];
    const onHold = Array.isArray(onHoldData) ? [...onHoldData] : [];

    if (labels.length > 20) {{
      labels.splice(20);
      solved.splice(20);
      inProgress.splice(20);
      inAnalysis.splice(20);
      onHold.splice(20);
    }}

    while (labels.length < 20) {{
      const last = labels.length ? labels[labels.length - 1] : null;
      const lastDate = weekToDate(last);
      const next = lastDate ? new Date(lastDate.getTime() + 7 * 86400000) : null;
      labels.push(next ? dateToWeekKey(next) : `W+${{labels.length + 1}}`);
      solved.push(0);
      inProgress.push(0);
      inAnalysis.push(0);
      onHold.push(0);
    }}

    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [
          {{
            label: 'OnHold',
            data: onHold,
            backgroundColor: '#9ca3af',
            borderColor: '#64748b',
            borderWidth: 1,
            stack: 'release-time'
          }},
          {{
            label: 'InAnalysis',
            data: inAnalysis,
            backgroundColor: '#f59e0b',
            borderColor: '#d97706',
            borderWidth: 1,
            stack: 'release-time'
          }},
          {{
            label: 'InProgress',
            data: inProgress,
            backgroundColor: '#3b82f6',
            borderColor: '#2563eb',
            borderWidth: 1,
            stack: 'release-time'
          }},
          {{
            label: 'Solved',
            data: solved,
            backgroundColor: '#10b981',
            borderColor: '#0f9b6f',
            borderWidth: 1,
            stack: 'release-time'
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {{
          legend: {{
            display: true,
            position: 'top',
            labels: {{
              font: {{ size: 11, weight: '600' }},
              padding: 12,
              usePointStyle: true
            }}
          }}
        }},
        scales: {{
          x: {{
            stacked: true,
            title: {{ display: true, text: 'Time', font: {{ weight: '600' }} }},
            grid: {{ display: false }}
          }},
          y: {{
            stacked: true,
            beginAtZero: true,
            title: {{ display: true, text: 'RootCause count', font: {{ weight: '600' }} }},
            grid: {{ color: 'rgba(0, 0, 0, 0.06)' }}
          }}
        }}
      }}
    }});
  }}

  createStatusBySymptomChart(
    'rc-timeline-chart-overall',
    {json.dumps(overall_chart_labels)},
    {json.dumps(overall_chart_solved)},
    {json.dumps(overall_chart_inprogress)},
    {json.dumps(overall_chart_inanalysis)},
    {json.dumps(overall_chart_onhold)}
  );

  createReleaseOverTimeChart(
    'rc-timeline-chart-release',
    {json.dumps(release_time_labels)},
    {json.dumps(release_time_solved)},
    {json.dumps(release_time_inprogress)},
    {json.dumps(release_time_inanalysis)},
    {json.dumps(release_time_onhold)}
  );
"""

    # Build unmatched-ticket category breakdown from Siroforce classified tickets
    _unmatched_section = ""
    _classified_path = BASE_DIR.parent / "Siroforce_Evaluation" / "output" / "tickets_classified.json"
    if _classified_path.exists():
        with open(_classified_path, encoding="utf-8") as f:
            _classified = json.load(f)
        _matched_ids = {tid for s in symptoms for tid in s.get("ticket_ids", [])}
        _unmatched_tickets = [
            t for t in _classified.get("tickets", [])
            if t.get("ticket_id") not in _matched_ids
        ]
        _unmatched_total = len(_unmatched_tickets)
        from collections import Counter as _Counter
        _cat_counts = _Counter(t.get("primary", "Unknown/Other") for t in _unmatched_tickets)
        _cat_rows = ""
        _prio_colors_cat = [
            "#c0392b", "#e67e22", "#2980b9", "#27ae60",
            "#8e44ad", "#1a6b8a", "#7f8c8d", "#2c3e50", "#d35400",
        ]
        for _i, (_cat, _cnt) in enumerate(sorted(_cat_counts.items(), key=lambda x: -x[1])):
            _pct = round(_cnt / total * 100, 1) if total else 0
            _pct_unmatched = round(_cnt / _unmatched_total * 100, 1) if _unmatched_total else 0
            _bar_w = int(_cnt / max(_cat_counts.values()) * 180)
            _col = _prio_colors_cat[_i % len(_prio_colors_cat)]
            _cat_rows += (
                f'<tr>'
                f'<td style="padding:7px 10px;font-weight:500">{_cat}</td>'
                f'<td style="padding:7px 10px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600">{_cnt:,}</td>'
                f'<td style="padding:7px 10px;text-align:right;font-variant-numeric:tabular-nums">{_pct} %</td>'
                f'</tr>'
            )
        _unmatched_section = f"""
  <section style="margin-bottom:28px">
    <h2 style="font-size:1.1em;margin-bottom:4px;color:var(--accent)">Unmatched Tickets — Category Breakdown</h2>
    <p style="font-size:0.83em;color:#888;margin-bottom:14px">{_unmatched_total:,} tickets ({round(_unmatched_total/total*100,1) if total else 0}% of {total:,} total) could not be assigned to any tracked symptom.</p>
    <table>
      <thead>
        <tr>
          <th>Category</th>
          <th style="text-align:right">Total</th>
          <th style="text-align:right">% Total</th>
        </tr>
      </thead>
      <tbody>{_cat_rows}</tbody>
    </table>
  </section>"""

    # Build R&D backlog section
    _status_styles = {
        "backlog":     ("background:#6c757d;color:white", "Backlog"),
        "in_progress": ("background:#e67e22;color:white", "In Progress"),
        "done":        ("background:#27ae60;color:white", "Done"),
    }
    _backlog_rows = ""
    for item in backlog_items:
        st = item.get("status", "backlog")
        badge_style, badge_label = _status_styles.get(st, _status_styles["backlog"])
        item_html = _backlog_item_html(item)
        _backlog_rows += (
            f'<tr>'
            f'<td style="padding:8px 10px"><span style="border-radius:4px;padding:2px 8px;font-size:0.8em;font-weight:600;{badge_style}">{badge_label}</span></td>'
            f'<td style="padding:8px 10px">{item_html}</td>'
            f'</tr>'
        )
    backlog_section = f"""
  <section style="margin-bottom:28px">
    <h2 style="font-size:1.1em;margin-bottom:12px;color:var(--accent)">R&amp;D Improvement Backlog</h2>
    <table>
      <thead>
        <tr>
          <th style="width:140px">Status</th>
          <th>Item</th>
        </tr>
      </thead>
      <tbody>{_backlog_rows}</tbody>
    </table>
  </section>""" if backlog_items else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Symptom Root Cause Ticket Evaluation</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --card: #ffffff;
      --border: #dde3ea;
      --text: #1a2433;
      --muted: #667788;
      --accent: #1a6b8a;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: var(--bg); color: var(--text); font-size: 14px; }}
    header {{ background: var(--accent); color: white; padding: 24px 32px; }}
    header h1 {{ font-size: 1.6em; font-weight: 600; }}
    header .meta {{ margin-top: 6px; font-size: 0.85em; opacity: 0.85; }}
    .container {{ max-width: 1400px; margin: 0 auto; padding: 24px 32px; }}

    /* KPI cards */
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
    .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px;
             padding: 16px 24px; min-width: 160px; flex: 1; }}
    .kpi .label {{ font-size: 0.78em; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
    .kpi .value {{ font-size: 2em; font-weight: 700; color: var(--accent); margin-top: 4px; }}
    .kpi .sub {{ font-size: 0.82em; color: var(--muted); margin-top: 2px; }}

    section {{ background: var(--card); border: 1px solid var(--border);
               border-radius: 8px; padding: 24px; margin-bottom: 28px; }}
    section h2 {{ font-size: 1.1em; margin-bottom: 16px; }}
    .group-total {{ font-size: 0.8em; font-weight: 400; color: var(--muted);
                   background: #f0f4f8; padding: 2px 8px; border-radius: 12px;
                   margin-left: 10px; }}

    table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
    th {{ background: #f0f4f8; padding: 8px 10px; text-align: left;
          font-weight: 600; border-bottom: 2px solid var(--border);
          white-space: nowrap; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #f8fafc; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}

    .symptom-name {{ font-weight: 500; min-width: 200px; }}

    /* Bar chart */
    .bar-wrap {{ display: flex; align-items: center; gap: 8px; min-width: 160px; }}
    .bar {{ height: 16px; border-radius: 3px; min-width: 2px; transition: width .3s; }}
    .bar-val {{ font-size: 0.9em; font-weight: 600; white-space: nowrap; }}

    /* Trend */
    .trend-cell {{ white-space: nowrap; font-weight: 600; }}
    .trend-up-strong {{ color: #c0392b; }}
    .trend-up {{ color: #e67e22; }}
    .trend-stable {{ color: #27ae60; }}
    .trend-down {{ color: #2980b9; }}
    .trend-down-strong {{ color: #1a6b8a; }}
    .trend-new {{ color: #8e44ad; font-style: italic; }}

    /* Keywords */
    .kw-cell {{ font-size: 0.78em; color: var(--muted); max-width: 300px;
                overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    code {{ background: #f0f4f8; border-radius: 3px; padding: 1px 4px;
            font-family: monospace; font-size: 0.9em; }}

    /* Summary */
    #summary {{ margin-bottom: 36px; }}
    #summary h2, #overview h2 {{ font-size: 1.2em; margin-bottom: 16px; color: var(--accent); }}

    /* Keyword tooltip */
    [data-kw] {{ position: relative; cursor: help; border-bottom: 1px dashed #aaa; }}
    [data-kw]::after {{
      content: attr(data-kw);
      position: absolute; left: 0; top: 100%; margin-top: 6px;
      background: #1a2433; color: #fff; border-radius: 6px;
      padding: 8px 12px; font-size: 0.78em; font-weight: 400;
      white-space: pre-wrap; max-width: 420px; z-index: 100;
      box-shadow: 0 4px 12px rgba(0,0,0,.25);
      pointer-events: none; opacity: 0; transition: opacity .15s;
    }}
    [data-kw]:hover::after {{ opacity: 1; }}

    footer {{ text-align: center; color: var(--muted); font-size: 0.82em;
              padding: 24px; border-top: 1px solid var(--border); }}

    /* Filter bar */
    .filter-bar {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px;
                   padding: 16px 24px; margin-bottom: 24px;
                   display: flex; align-items: flex-start; gap: 24px; flex-wrap: wrap; }}
    .filter-group {{ display: flex; flex-direction: column; gap: 6px; }}
    .filter-bar label {{ font-size: 0.78em; font-weight: 600; color: var(--muted);
                         text-transform: uppercase; letter-spacing: .04em; }}
    .filter-bar select {{ border: 1px solid var(--border); border-radius: 6px;
                          padding: 6px 10px; font-size: 0.88em; background: white;
                          color: var(--text); cursor: pointer; }}
    .filter-bar select:focus {{ outline: 2px solid var(--accent); }}
    .filter-row-hidden {{ display: none !important; }}
    /* Bug detail modal */
    #bug-modal {{ display:none;position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:1000;align-items:center;justify-content:center }}
    #bug-modal-inner {{ background:#fff;border-radius:10px;max-width:720px;width:92%;max-height:82vh;overflow-y:auto;padding:28px 32px;position:relative;box-shadow:0 8px 36px rgba(0,0,0,.28) }}
    #bug-modal-inner .close-btn {{ position:absolute;top:14px;right:18px;background:none;border:none;font-size:1.5em;cursor:pointer;color:#888;line-height:1 }}
    #bug-modal-inner .close-btn:hover {{ color:#c0392b }}
    table tr[onclick]:hover td {{ background:#fff8e8 !important }}
    /* Ticket search */
    #ticket-search-box {{ background:var(--card);border:1px solid var(--border);border-radius:8px;
                          padding:16px 24px;margin-bottom:24px; }}
    #ticket-search-box h3 {{ font-size:0.95em;font-weight:600;margin-bottom:10px;color:var(--accent); }}
    #ticket-search-input {{ border:1px solid var(--border);border-radius:6px;padding:7px 12px;
                            font-size:0.92em;width:280px;transition:border .15s; }}
    #ticket-search-input:focus {{ outline:2px solid var(--accent);border-color:var(--accent); }}
    #ticket-search-results {{ margin-top:12px;font-size:0.88em; }}
    .ts-result {{ border:1px solid #ffc107;background:#fffbea;border-radius:6px;
                  padding:10px 14px;margin-bottom:8px; }}
    .ts-result-header {{ font-weight:600;color:#856404;margin-bottom:4px; }}
    .ts-result-row {{ display:flex;gap:24px;flex-wrap:wrap;margin-top:4px;font-size:0.85em;color:#444; }}
    .ts-label {{ font-weight:600;color:#666; }}
    .ts-badge {{ display:inline-block;border-radius:3px;padding:1px 6px;font-size:0.8em;
                 font-weight:600;background:#e2e8f0;color:#333;margin-left:4px; }}
    .ts-not-found {{ color:#888;font-style:italic; }}
    .status-scope-toggle {{ display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px; }}
    .status-scope-btn {{
      border:1px solid #1a6b8a;
      background:white;
      color:#1a6b8a;
      border-radius:6px;
      padding:6px 12px;
      font-size:0.85em;
      font-weight:600;
      cursor:pointer;
    }}
    .status-scope-btn.active {{ background:#1a6b8a;color:white; }}
  </style>
</head>
<body>
<header>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:24px">
    <div style="flex:1">
      <h1>Symptom Root Cause — Ticket Trend Evaluation</h1>
      <div class="meta">Generated: {generated} &nbsp;|&nbsp; Source: tickets_raw.json{f' &nbsp;|&nbsp; Jira Import: {jira_import_date}' if jira_import_date else ''}</div>
      <!-- Filter bar inside header -->
      <div style="margin-top:18px;display:flex;flex-direction:column;gap:10px;font-size:0.92em">
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-weight:600;color:white;min-width:160px">Region Filter</span>
          <select id="f-region" onchange="applyFilter()" style="padding:4px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.3);background:white;color:#1a2433;font-size:0.9em">
            <option value="">ALL</option>
            <option value="US">US</option>
            <option value="EU">EU</option>
            <option value="REST">REST</option>
          </select>
          <span style="color:rgba(255,255,255,0.55);font-size:0.82em">US = Support Hub US &nbsp; EU = known EU codes &nbsp; REST = all others</span>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-weight:600;color:white;min-width:160px">Priority</span>
          <select id="f-prio" onchange="applyFilter()" style="padding:4px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.3);background:white;color:#1a2433;font-size:0.9em">
            <option value="">All Priorities</option>
            <option value="1">Priority 1</option>
            <option value="2">Priority 2</option>
            <option value="3">Priority 3</option>
            <option value="4">Priority 4</option>
          </select>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-weight:600;color:white;min-width:160px">AI Category</span>
          <select id="f-cat" onchange="applyFilter()" style="padding:4px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.3);background:white;color:#1a2433;font-size:0.9em">
            <option value="">All AI Categories</option>
            {ai_options}
          </select>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-weight:600;color:white;min-width:160px">Record Type Filter (Multi-select)</span>
          <label style="color:white;font-weight:400;cursor:pointer"><input type="checkbox" id="cb-complaint" checked onchange="applyFilter()"> Complaint</label>
          <label style="color:white;font-weight:400;cursor:pointer"><input type="checkbox" id="cb-inquiry" checked onchange="applyFilter()"> Inquiry</label>
          <label style="color:white;font-weight:400;cursor:pointer"><input type="checkbox" id="cb-rest" checked onchange="applyFilter()"> Rest</label>
          <button onclick="resetFilters()" style="margin-left:16px;padding:4px 12px;border:1px solid rgba(255,255,255,0.4);border-radius:4px;background:rgba(255,255,255,0.15);cursor:pointer;font-size:0.88em;color:white">Reset</button>
          <span id="filter-count" style="font-size:0.8em;color:rgba(255,255,255,0.6);margin-left:8px"></span>
        </div>
      </div>
    </div>
    {f'<img id="header-img" src="data:image/png;base64,{img_b64}" alt="Market Symptom Overview" onclick="toggleHeaderImg()" style="height:200px;border-radius:6px;opacity:0.95;flex-shrink:0;align-self:flex-start;cursor:zoom-in;transition:all .25s" title="Click to enlarge" />' if img_b64 else ''}
  </div>
</header>

<div class="container">

  <!-- KPI Cards -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Total Tickets</div>
      <div class="value" id="kpi-total">{total:,}</div>
      <div class="sub" id="kpi-year-breakdown">{year_breakdown}</div>
    </div>
    <div class="kpi">
      <div class="label">Tickets Mapped</div>
      <div class="value" id="kpi-mapped">{mapped:,}</div>
      <div class="sub" id="kpi-mapped-pct">{round(mapped/total*100,1) if total else 0}% of total</div>
    </div>
    <div class="kpi">
      <div class="label">Symptoms Tracked</div>
      <div class="value">{len(symptoms)}</div>
      <div class="sub">in {len({s.get("ai_category","") for s in symptoms if s.get("ai_category")})} AI categories</div>
    </div>
    <div class="kpi">
      <div class="label">Analysis Period</div>
      <div class="value" style="font-size:1.1em">{date_range}</div>
      <div class="sub">Oldest → newest ticket</div>
    </div>
  </div>

  <!-- Overview Charts Panel -->
  <section id="overview" style="margin-bottom:32px">
    <h2>Overview & Coverage Analysis</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px;margin-bottom:24px">
      <!-- Chart 1: Matched vs Unmatched -->
      <div style="background:#f8fafc;border:1px solid #d0dde8;border-radius:8px;padding:20px">
        <h3 style="margin:0 0 16px 0;font-size:0.95em;color:#333">Siroforce Tickets: Symptom Coverage</h3>
        <div style="width:200px;height:200px;margin:0 auto">
          <canvas id="chart1" width="200" height="200"></canvas>
        </div>
        <div style="margin-top:8px;text-align:center;font-size:0.82em;color:#555">
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:3px"></span>Matched</span>
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#f59e0b;border-radius:2px;margin-right:3px"></span>Intermittent Connectivity</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#94a3b8;border-radius:2px;margin-right:3px"></span>Unmatched</span>
        </div>
        <div style="margin-top:12px;font-size:0.82em;color:#555">
          <div style="display:flex;gap:16px">
            <span>Matched: <strong>{sum(s['total'] for s in symptoms):,}</strong></span>
            <span>Unmatched: <strong>{total - sum(s['total'] for s in symptoms):,}</strong></span>
          </div>
          <div style="margin-top:4px;color:#888;font-size:0.95em">of which IC: <strong>{ic_siroforce:,}</strong></div>
          <div style="margin-top:6px;border-top:1px solid #d0dde8;padding-top:6px;color:#888">Ticket Base: <strong>{total:,}</strong></div>
        </div>
      </div>
      <!-- Chart 2: Assigned vs Unassigned -->
      <div style="background:#f8fafc;border:1px solid #d0dde8;border-radius:8px;padding:20px">
        <h3 style="margin:0 0 16px 0;font-size:0.95em;color:#333">Jira-Bug Ticket (Y3839): Symptom Coverage</h3>
        <div style="width:200px;height:200px;margin:0 auto">
          <canvas id="chart2" width="200" height="200"></canvas>
        </div>
        <div style="margin-top:8px;text-align:center;font-size:0.82em;color:#555">
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:3px"></span>Matched</span>
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#f59e0b;border-radius:2px;margin-right:3px"></span>Intermittent Connectivity</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#94a3b8;border-radius:2px;margin-right:3px"></span>Unmatched</span>
        </div>
        <div style="margin-top:12px;font-size:0.82em;color:#555">
          <div style="display:flex;gap:16px">
            <span>Matched: <strong>{jira_assigned:,}</strong></span>
            <span>Unmatched: <strong>{jira_unassigned:,}</strong></span>
          </div>
          <div style="margin-top:4px;color:#888;font-size:0.95em">of which IC: <strong>{ic_hw_total + ic_sw_total + ic_cm_total}</strong></div>
          <div style="margin-top:6px;border-top:1px solid #d0dde8;padding-top:6px;color:#888">Ticket Base: <strong>{jira_assigned + jira_unassigned:,}</strong></div>
        </div>
      </div>
      <!-- Chart 3: Intermittent Connectivity HW vs SW -->
      <div style="background:#f8fafc;border:1px solid #d0dde8;border-radius:8px;padding:20px">
        <h3 style="margin:0 0 16px 0;font-size:0.95em;color:#333">Release Scope: Stabilize the Connectivity</h3>
        <div style="width:200px;height:200px;margin:0 auto;position:relative">
          <canvas id="chart3" width="200" height="200"></canvas>
          <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none">
            <span style="font-size:1.4em;font-weight:700;color:rgba(180,0,0,0.22);transform:rotate(-30deg);white-space:nowrap;letter-spacing:0.05em">DRAFT / TBD</span>
          </div>
        </div>
        <div style="margin-top:8px;text-align:center;font-size:0.82em;color:#555">
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#16a34a;border-radius:2px;margin-right:3px"></span>CM</span>
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#e67e22;border-radius:2px;margin-right:3px"></span>HW</span>
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:3px"></span>SW</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#94a3b8;border-radius:2px;margin-right:3px"></span>Other Symptoms</span>
        </div>
        <div style="margin-top:12px;font-size:0.82em;color:#555">
          <div style="display:flex;gap:16px;flex-wrap:wrap">
            <span>CM: <strong>{ic_cm_total}</strong></span>
            <span>HW: <strong>{ic_hw_total}</strong></span>
            <span>SW: <strong>{ic_sw_total}</strong></span>
            <span>Other Symptoms: <strong>{jira_assigned - ic_hw_total - ic_sw_total - ic_cm_total}</strong></span>
          </div>
          <div style="margin-top:6px;border-top:1px solid #d0dde8;padding-top:6px;color:#888">Ticket Base: <strong>{jira_assigned}</strong> matched</div>
        </div>
        <div style="margin-top:12px;font-size:0.8em;color:#444">
          <div style="font-weight:600;margin-bottom:4px;color:#555">Top Root Causes &mdash; Symptom: Intermittent Connectivity:</div>
          <ol style="margin:0;padding-left:18px;line-height:1.7">{ic_top3_html}</ol>
        </div>
      </div>
    </div>
  </section>

  <!-- Status Tracker -->
  <section>
    <h2 style="border-left:6px solid #1a6b8a;padding-left:12px">Status Tracker
      <span class="group-total">{sum(global_status_counts.values())} Status Entries</span>
    </h2>

    <div class="status-scope-toggle">
      <button id="status-scope-btn-overall" class="status-scope-btn active" type="button" onclick="setStatusScope('overall')">Overall</button>
      <button id="status-scope-btn-release" class="status-scope-btn" type="button" onclick="setStatusScope('release')">Upcoming Release</button>
    </div>
    
    <!-- Current Status Distribution -->
    <div id="status-scope-overall" style="margin-bottom:28px">
      <div style="font-size:0.9em;font-weight:600;margin-bottom:12px;color:var(--muted);text-transform:uppercase">Overall Root Cause Current Week Status</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(120px, 1fr));gap:12px">
        {global_status_summary}
      </div>
    </div>

    <div id="status-scope-release" style="display:none;margin-bottom:28px">
      <div style="font-size:0.9em;font-weight:600;margin-bottom:12px;color:var(--muted);text-transform:uppercase">Upcoming Release Root Cause Current Week Status</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(120px, 1fr));gap:12px">
        {release_status_summary}
      </div>
    </div>

    <!-- Timeline Chart -->
    <div style="margin-bottom:28px">
      <div id="status-dev-title" style="font-size:0.9em;font-weight:600;margin-bottom:12px;color:var(--muted);text-transform:uppercase">Current Root Cause Status</div>
      <div style="background:#f8fafc;border:1px solid #d0dde8;border-radius:8px;padding:16px">
        <div id="status-chart-overall">
          <canvas id="rc-timeline-chart-overall" height="90"></canvas>
        </div>
        <div id="status-chart-release" style="display:none">
          <canvas id="rc-timeline-chart-release" height="90"></canvas>
        </div>
      </div>
    </div>

  </section>

  <!-- Overall Summary -->
    <section id="summary">
    <h2>Siroforce Symptoms Evaluation</h2>
    <table>
      <thead>
        <tr>
          <th>Priority</th>
          <th>Symptom</th>
          <th>AI Category</th>
          <th class="num">Total</th>
          <th class="num">% Total</th>
          <th class="num">{y1}</th>
          <th class="num">{y2}</th>
          <th>Trend {y1}{y2}</th>
        </tr>
      </thead>
      <tbody>{summary_rows}</tbody>
    </table>
  </section>

  <!-- Symptoms and Root Causes -->
  {_unmatched_section}
  <section>
    <h2 style="font-size:1.1em;margin-bottom:12px;color:var(--accent)">Symptoms and Root Causes</h2>
    <!-- Jira coverage bar -->
    <div style="display:flex;align-items:center;gap:18px;background:#f8fafc;border:1px solid #d0dde8;border-radius:8px;padding:10px 18px;margin-bottom:16px;flex-wrap:wrap">
      <span style="font-size:0.9em;color:#555;white-space:nowrap">Jira Bugs / Improvements:</span>
      <span style="font-weight:700;font-size:1em">{jira_total_bugs} total</span>
      <div style="flex:1;min-width:120px;background:#e0e8f0;border-radius:4px;height:12px;overflow:hidden">
        <div style="width:{jira_pct}%;background:#2563eb;height:12px;border-radius:4px;transition:width .4s"></div>
      </div>
      <span style="white-space:nowrap;font-size:0.9em">
        <span style="color:#2563eb;font-weight:600">{jira_assigned} assigned</span>
        &nbsp;·&nbsp;
        <span style="color:#888">{jira_unassigned} unassigned</span>
        &nbsp;·&nbsp;
        <span style="color:#444;font-weight:600">{jira_pct} %</span>
      </span>
    </div>
    <table>
      <thead>
        <tr>
          <th style="width:110px">Priority</th>
          <th style="width:260px">Symptom / AI Category</th>
          <th>Root Causes</th>
          <th style="width:130px">Selected for Release</th>
          <th style="width:120px">Status</th>
        </tr>
      </thead>
      <tbody>{rc_section_rows}</tbody>
    </table>
    <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-top:14px;padding:0 4px 4px 4px">
      <div style="font-size:0.88em;color:#475569;line-height:1.5">
        {editable_rc_count} RCs without Jira Bugs can be updated via dropdown and written directly into rc_status.json and rc_status_history.json.
      </div>
      <div style="display:flex;align-items:center;gap:12px;justify-content:flex-end;flex-wrap:wrap">
        <span id="status-save-message" style="font-size:0.88em;color:#475569"></span>
        <button id="confirm-status-btn" onclick="confirmStatus()" style="background:#2563eb;color:white;border:none;border-radius:8px;padding:10px 16px;font-size:0.9em;font-weight:600;cursor:pointer">Confirm Status</button>
      </div>
    </div>
  </section>

  <section>
  {backlog_section}

  <!-- Ticket Search -->
  <div id="ticket-search-box">
    <h3>&#128269; Jira Ticket Search</h3>
    <input id="ticket-search-input" type="text" placeholder="e.g. Y3839-734 or 570, 538"
           oninput="ticketSearch(this.value)" autocomplete="off" spellcheck="false" />
    <div id="ticket-search-results"></div>
  </div>

</div>

<!-- Bug detail modal -->
<div id="bug-modal" onclick="closeBugModal()">
  <div id="bug-modal-inner" onclick="event.stopPropagation()">
    <button class="close-btn" onclick="closeBugModal()">&times;</button>
    <div id="bug-modal-content"></div>
  </div>
</div>

<footer>
  Symptom Root Cause Ticket Evaluation &nbsp;|&nbsp; Dentsply Sirona &nbsp;|&nbsp; {datetime.now().year}
</footer>
{f'<script>{chartjs_inline}</script>' if chartjs_inline else '<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>'}
<script>
// Initialize pie charts
document.addEventListener('DOMContentLoaded', function() {{
  // Chart 1: Matched vs Unmatched
  const ctx1 = document.getElementById('chart1').getContext('2d');
  new Chart(ctx1, {{
    type: 'doughnut',
    data: {{
      labels: ['Matched', 'Unmatched'],
      datasets: [
        {{
          label: 'outer',
          data: [{sum(s['total'] for s in symptoms)}, {total - sum(s['total'] for s in symptoms)}],
          backgroundColor: ['#2563eb', '#94a3b8'],
          borderColor: ['#1e40af', '#64748b'],
          borderWidth: 2,
          weight: 2,
        }},
        {{
          label: 'inner',
          data: [{ic_siroforce}, {sum(s['total'] for s in symptoms) - ic_siroforce}, {total - sum(s['total'] for s in symptoms)}],
          backgroundColor: ['#f59e0b', '#2563eb', '#94a3b8'],
          borderColor: ['#d97706', '#1e40af', '#64748b'],
          borderWidth: 1,
          weight: 1,
        }}
      ]
    }},
    options: {{
      responsive: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.label + ': ' + ctx.parsed + ' tickets'; }} }} }}
      }}
    }}
  }});

  // Chart 2: Matched vs Unmatched, with IC overlay on inner ring
  const ctx2 = document.getElementById('chart2').getContext('2d');
  new Chart(ctx2, {{
    type: 'doughnut',
    data: {{
      labels: ['Intermittent Connectivity', 'Other Matched', 'Unmatched'],
      datasets: [
        {{
          label: 'outer',
          data: [{jira_assigned}, {jira_unassigned}],
          backgroundColor: ['#2563eb', '#94a3b8'],
          borderColor: ['#1e40af', '#64748b'],
          borderWidth: 2,
          weight: 2,
        }},
        {{
          label: 'inner',
          data: [{ic_hw_total + ic_sw_total}, {jira_assigned - ic_hw_total - ic_sw_total}, {jira_unassigned}],
          backgroundColor: ['#f59e0b', '#2563eb', '#94a3b8'],
          borderColor: ['#d97706', '#1e40af', '#64748b'],
          borderWidth: 1,
          weight: 1,
        }}
      ]
    }},
    options: {{
      responsive: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.label + ': ' + ctx.parsed + ' tickets'; }} }} }}
      }}
    }}
  }});

  // Chart 3: Intermittent Connectivity HW vs SW vs CM vs other assigned tickets
  const ctx3 = document.getElementById('chart3').getContext('2d');
  new Chart(ctx3, {{
    type: 'doughnut',
    data: {{
      labels: ['HW', 'SW', 'CM', 'Other Symptoms'],
      datasets: [{{
        data: [{ic_hw_total}, {ic_sw_total}, {ic_cm_total}, {jira_assigned - ic_hw_total - ic_sw_total - ic_cm_total}],
        backgroundColor: ['#e67e22', '#2563eb', '#16a34a', '#94a3b8'],
        borderColor: ['#d35400', '#1e40af', '#0d8659', '#64748b'],
        borderWidth: 2
      }}]
    }},
    options: {{
      responsive: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.label + ': ' + ctx.parsed + ' Tickets'; }} }} }}
      }}
    }}
  }});
  
  {rc_timeline_chart_js}
}});
</script>
<script>
const SYMPTOMS = {symptom_data_js};
const YEARS = {_json.dumps(years)};
const TOTAL_ALL = {total};
const TOTAL_BREAKDOWN = {total_breakdown_js};

function sumBreakdown(bd, regions, types) {{
  let n = 0;
  const regs = regions.length ? regions : Object.keys(bd);
  for (const r of regs) {{
    if (!bd[r]) continue;
    const typs = types.length ? types : Object.keys(bd[r]);
    for (const t of typs) {{
      n += bd[r][t] || 0;
    }}
  }}
  return n;
}}

function getFilteredTotal(bd, regions, types) {{
  let n = 0;
  const regs = regions.length ? regions : Object.keys(bd);
  for (const r of regs) {{
    if (!bd[r]) continue;
    const typs = types.length ? types : Object.keys(bd[r]);
    for (const t of typs) {{
      if (!bd[r][t]) continue;
      n += Object.values(bd[r][t]).reduce((a,b)=>a+b,0);
    }}
  }}
  return n;
}}

function getFilteredByYear(bd, regions, types) {{
  const byYear = {{}};
  const regs = regions.length ? regions : Object.keys(bd);
  for (const r of regs) {{
    if (!bd[r]) continue;
    const typs = types.length ? types : Object.keys(bd[r]);
    for (const t of typs) {{
      if (!bd[r][t]) continue;
      for (const [yr, cnt] of Object.entries(bd[r][t])) {{
        byYear[yr] = (byYear[yr]||0) + cnt;
      }}
    }}
  }}
  return byYear;
}}

function nf(n) {{ return n.toLocaleString(); }}

function applyFilter() {{
  const region = document.getElementById('f-region').value;
  const prio   = document.getElementById('f-prio').value;
  const cat    = document.getElementById('f-cat').value;
  const types  = [];
  if (document.getElementById('cb-complaint').checked) types.push('Complaint');
  if (document.getElementById('cb-inquiry').checked)   types.push('Inquiry');
  if (document.getElementById('cb-rest').checked)      types.push('Rest');
  const regions = region ? [region] : [];

  // Update Total Tickets KPI
  const filteredTotal = sumBreakdown(TOTAL_BREAKDOWN, regions, types);
  document.getElementById('kpi-total').textContent = nf(filteredTotal);
  const ybEl = document.getElementById('kpi-year-breakdown');
  if (ybEl && regions.length === 0 && types.length === 0) {{
    // reset to all
  }}

  // Calculate grand total of mapped for % 
  let grandMapped = 0;
  SYMPTOMS.forEach(s => {{ grandMapped += getFilteredTotal(s.breakdown, regions, types); }});
  document.getElementById('kpi-mapped').textContent = nf(grandMapped);
  const pct = filteredTotal > 0 ? (grandMapped/filteredTotal*100).toFixed(1) : '0.0';
  document.getElementById('kpi-mapped-pct').textContent = pct + '% of total';

  const rows = document.querySelectorAll('#summary tbody tr');
  let visible = 0;
  rows.forEach((row, i) => {{
    const s = SYMPTOMS[i];
    if (!s) return;
    const prioMatch = !prio || String(s.priority) === prio;
    const catMatch  = !cat  || (Array.isArray(s.ai_category) ? s.ai_category.includes(cat) : s.ai_category === cat);
    if (!prioMatch || !catMatch) {{ row.classList.add('filter-row-hidden'); return; }}
    row.classList.remove('filter-row-hidden');
    visible++;

    const cnt = getFilteredTotal(s.breakdown, regions, types);
    const byYear = getFilteredByYear(s.breakdown, regions, types);
    const pctRow = filteredTotal > 0 ? (cnt/filteredTotal*100).toFixed(1) : '0.0';

    row.querySelector('.dyn-total').textContent = nf(cnt);
    row.querySelector('.dyn-pct').textContent = pctRow + '%';

    YEARS.forEach((yr, j) => {{
      const el = row.querySelector('.dyn-yr-'+j);
      if (el) el.textContent = nf(byYear[yr]||0);
    }});

    const y1 = YEARS.length>=2 ? YEARS[YEARS.length-2] : '';
    const y2 = YEARS.length>=2 ? YEARS[YEARS.length-1] : '';
    const c1 = byYear[y1]||0, c2 = byYear[y2]||0;
    const trendEl = row.querySelector('.dyn-trend');
    if (trendEl && c1>0) {{
      const tp = ((c2-c1)/c1*100).toFixed(0);
      const cls = tp>50?'trend-up-strong':tp>10?'trend-up':tp>-10?'trend-stable':tp>-50?'trend-down':'trend-down-strong';
      const arrow = tp>50?'▲▲ +':tp>10?'▲ +':tp>-10?'→ ':tp>-50?'▼ ':'▼▼ ';
      trendEl.className = 'trend-cell '+cls;
      trendEl.textContent = arrow+tp+'%';
    }}
  }});

  const lbl = visible<SYMPTOMS.length ? `Showing ${{visible}} of ${{SYMPTOMS.length}} symptoms` : '';
  document.getElementById('filter-count').textContent = lbl;
}}

function toggleHeaderImg() {{
  const img = document.getElementById('header-img');
  if (!img) return;
  const expanded = img.getAttribute('data-expanded') === '1';
  if (expanded) {{
    img.style.cssText = 'height:200px;border-radius:6px;opacity:0.95;flex-shrink:0;align-self:flex-start;cursor:zoom-in;transition:all .25s';
    img.removeAttribute('data-expanded');
  }} else {{
    img.style.position = 'fixed';
    img.style.top = '50%';
    img.style.left = '50%';
    img.style.transform = 'translate(-50%,-50%)';
    img.style.height = 'auto';
    img.style.width = 'auto';
    img.style.maxWidth = '90vw';
    img.style.maxHeight = '90vh';
    img.style.zIndex = '2000';
    img.style.boxShadow = '0 12px 48px rgba(0,0,0,0.6)';
    img.style.borderRadius = '8px';
    img.style.cursor = 'zoom-out';
    img.setAttribute('data-expanded', '1');
  }}
}}

function toggleJira(id) {{
  const el = document.getElementById(id);
  if (el) el.style.display = el.style.display === 'none' ? 'table' : 'none';
}}

function setStatusScope(scope) {{
  const overallBlock = document.getElementById('status-scope-overall');
  const releaseBlock = document.getElementById('status-scope-release');
  const overallChart = document.getElementById('status-chart-overall');
  const releaseChart = document.getElementById('status-chart-release');
  const statusDevTitle = document.getElementById('status-dev-title');
  const overallBtn = document.getElementById('status-scope-btn-overall');
  const releaseBtn = document.getElementById('status-scope-btn-release');
  if (overallBlock) overallBlock.style.display = scope === 'overall' ? 'block' : 'none';
  if (releaseBlock) releaseBlock.style.display = scope === 'release' ? 'block' : 'none';
  if (overallChart) overallChart.style.display = scope === 'overall' ? 'block' : 'none';
  if (releaseChart) releaseChart.style.display = scope === 'release' ? 'block' : 'none';
  if (statusDevTitle) statusDevTitle.textContent = scope === 'overall' ? 'Current Root Cause Status' : 'Upcoming release root causes over time';
  if (overallBtn) overallBtn.classList.toggle('active', scope === 'overall');
  if (releaseBtn) releaseBtn.classList.toggle('active', scope === 'release');
}}

const JIRA_BUGS = {jira_bugs_js};
const TICKET_INDEX = {ticket_index_js};
const RC_STATUS_DATA = {rc_status_data_js};
const RC_STATUS_HISTORY = {rc_status_history_data_js};
const RELEASE_RC_KEYS = new Set({release_rc_keys_js});
const WINDOWS_USER = {windows_user_js};
const JIRA_RC_FLAGS = {jira_rc_flags_js};
const JIRA_RC_STATUSES = {jira_rc_statuses_js};
const JIRA_RC_TICKETS = {jira_rc_tickets_js};
const PRIO_COL = {{Urgent:'#c0392b',High:'#e67e22',Medium:'#2980b9',Low:'#7f8c8d',Lowest:'#95a5a6'}};

function normalizeStatusJs(status) {{
  if (status === 'Completed') return 'Solved';
  return status || '';
}}

function cloneJson(obj) {{
  return JSON.parse(JSON.stringify(obj));
}}

function statusFromRcEntry(entry, fallback = '') {{
  if (entry && typeof entry === 'object' && !Array.isArray(entry)) {{
    return normalizeStatusJs(entry.status || fallback);
  }}
  return normalizeStatusJs(entry || fallback);
}}

function normalizeRcKeyJs(text) {{
  if (!text) return '';
  let cleaned = String(text).replace('(SW-solution)', '');
  cleaned = cleaned.replace(/\s*\[(HW|SW|FW|CM)\]\s*$/i, '');
  cleaned = cleaned.replace(/\s+/g, ' ').trim().replace(/[\s,]+$/g, '');
  return cleaned.toLowerCase();
}}

function rcActionTypeFromName(rcName) {{
  const match = String(rcName || '').match(/\[(HW|SW|FW|CM)\]\s*$/i);
  if (!match) return '';
  return match[1].toUpperCase();
}}

function normalizeRcNameJs(text) {{
  if (!text) return '';
  return String(text).replace(/\s*\[(HW|SW|FW|CM)\]\s*$/i, '').trim();
}}

function rcLookupKey(symptom, rc) {{
  return `${{symptom}}\u0000${{normalizeRcKeyJs(rc)}}`;
}}

function getIsoWeek(date) {{
  const utcDate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = utcDate.getUTCDay() || 7;
  utcDate.setUTCDate(utcDate.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((utcDate - yearStart) / 86400000) + 1) / 7);
  return `${{utcDate.getUTCFullYear()}}-W${{String(weekNo).padStart(2, '0')}}`;
}}

function buildRcStatusPayload() {{
  const nextPayload = {{ rc_status: {{}}, selected_for_release: {{}} }};
  const selectedStatuses = new Map();
  const selectedRelease = new Map();
  document.querySelectorAll('.rc-status-select').forEach((selectEl) => {{
    selectedStatuses.set(rcLookupKey(selectEl.dataset.symptom, selectEl.dataset.rc), selectEl.value);
  }});
  document.querySelectorAll('.rc-release-select').forEach((selectEl) => {{
    selectedRelease.set(rcLookupKey(selectEl.dataset.symptom, selectEl.dataset.rc), selectEl.value === 'Yes' ? 'Yes' : 'No');
  }});

  for (const [symptom, rcMap] of Object.entries((RC_STATUS_DATA && RC_STATUS_DATA.rc_status) || {{}})) {{
    nextPayload.rc_status[symptom] = {{}};
    nextPayload.selected_for_release[symptom] = {{}};
    for (const [rc, rawEntry] of Object.entries(rcMap || {{}})) {{
      const normalizedRcName = normalizeRcNameJs(rc);
      const hasJira = Boolean(JIRA_RC_FLAGS[symptom] && JIRA_RC_FLAGS[symptom][rc]);
      const key = rcLookupKey(symptom, rc);
      const fallbackRelease = RELEASE_RC_KEYS.has(normalizeRcKeyJs(rc)) ? 'Yes' : 'No';
      const selectedState = selectedRelease.get(key) || fallbackRelease;
      const actionType = rcActionTypeFromName(rc) || (rawEntry && typeof rawEntry === 'object' ? String(rawEntry.action_type || '').toUpperCase() : '');
      nextPayload.selected_for_release[symptom][normalizedRcName] = selectedState;
      let nextStatus = statusFromRcEntry(rawEntry, 'OnHold');
      if (hasJira) {{
        const ticketEntries = (JIRA_RC_TICKETS[symptom] && JIRA_RC_TICKETS[symptom][rc]) || [];
        const jiraTicketList = [];
        for (const ticketEntry of ticketEntries) {{
          const ticketKey = String(ticketEntry && ticketEntry.key || '').trim();
          const rawJiraStatus = String(ticketEntry && ticketEntry.status || '').trim();
          const mappedTicketStatus = mapJiraTicketStatus(rawJiraStatus);
          if (ticketKey) {{
            jiraTicketList.push({{
              key: ticketKey,
              status: mappedTicketStatus,
              jira_status: rawJiraStatus,
              selected: selectedState,
            }});
          }}
        }}
        nextPayload.rc_status[symptom][normalizedRcName] = {{
          status: '',
          action_type: actionType,
          jira_tickets: jiraTicketList,
        }};
        continue;
      }} else if (nextStatus !== 'Solved') {{
        nextStatus = selectedStatuses.get(key) || 'OnHold';
      }}
      nextPayload.rc_status[symptom][normalizedRcName] = {{
        status: nextStatus,
        selected: selectedState,
        action_type: actionType,
      }};
    }}
  }}

  return nextPayload;
}}

function mapJiraTicketStatus(status) {{
  const normalized = String(status || '').trim().toUpperCase();
  if (normalized === 'ONHOLD') return 'OnHold';
  if (normalized === 'INANALYSIS') return 'InAnalysis';
  if (normalized === 'INPROGRESS') return 'InProgress';
  if (normalized === 'SOLVED') return 'Solved';
  if (normalized === 'IN PROGRESS' || normalized === 'IN QA') return 'InProgress';
  if (normalized === 'ACCEPTED') return 'InAnalysis';
  if (normalized === 'SOLVED' || normalized === 'DONE' || normalized === 'RESOLVED' || normalized === 'CLOSED') return 'Solved';
  if (normalized) return 'OnHold';
  return '';
}}

function deriveJiraRcStatus(statuses) {{
  const mappedStatuses = (statuses || []).map(mapJiraTicketStatus).filter(Boolean);
  if (!mappedStatuses.length) return '';
  if (mappedStatuses.includes('InProgress')) return 'InProgress';
  if (mappedStatuses.includes('InAnalysis')) return 'InAnalysis';
  if (mappedStatuses.includes('OnHold')) return 'OnHold';
  if (mappedStatuses.includes('Solved')) return 'Solved';
  return '';
}}

function buildHistoryRcStatusPayload(rcStatusPayload) {{
  const historyRcStatus = {{}};
  for (const [symptom, rcMap] of Object.entries((rcStatusPayload && rcStatusPayload.rc_status) || {{}})) {{
    const symptomEntries = {{}};
    for (const [rc, rcEntry] of Object.entries(rcMap || {{}})) {{
      if (!rcEntry || typeof rcEntry !== 'object' || Array.isArray(rcEntry)) continue;

      const ticketEntries = Array.isArray(rcEntry.jira_tickets) ? rcEntry.jira_tickets : null;
      if (ticketEntries && ticketEntries.length) {{
        const selectedTickets = ticketEntries
          .filter((ticket) => ticket && String(ticket.selected || '').trim().toLowerCase() === 'yes')
          .map((ticket) => cloneJson(ticket));
        if (!selectedTickets.length) continue;

        const nextEntry = cloneJson(rcEntry);
        nextEntry.jira_tickets = selectedTickets;
        symptomEntries[rc] = nextEntry;
        continue;
      }}

      const rcSelected = String(rcEntry.selected || '').trim().toLowerCase();
      if (rcSelected !== 'yes') continue;
      symptomEntries[rc] = cloneJson(rcEntry);
    }}
    if (Object.keys(symptomEntries).length) {{
      historyRcStatus[symptom] = symptomEntries;
    }}
  }}
  return {{ rc_status: historyRcStatus }};
}}

async function writeTextFile(dirHandle, fileName, content) {{
  const fileHandle = await dirHandle.getFileHandle(fileName, {{ create: true }});
  const writable = await fileHandle.createWritable();
  await writable.write(content);
  await writable.close();
}}

function openStatusHandleDb() {{
  return new Promise((resolve, reject) => {{
    const request = indexedDB.open('symptom-status-storage', 1);
    request.onupgradeneeded = () => {{
      const db = request.result;
      if (!db.objectStoreNames.contains('handles')) {{
        db.createObjectStore('handles');
      }}
    }};
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }});
}}

let outputDirHandleCache = null;
const DISABLE_DIRECTORY_PICKER = false;

async function loadStoredOutputDirHandle() {{
  const db = await openStatusHandleDb();
  return await new Promise((resolve, reject) => {{
    const tx = db.transaction('handles', 'readonly');
    const store = tx.objectStore('handles');
    const request = store.get('outputDir');
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  }});
}}

async function storeOutputDirHandle(dirHandle) {{
  const db = await openStatusHandleDb();
  await new Promise((resolve, reject) => {{
    const tx = db.transaction('handles', 'readwrite');
    const store = tx.objectStore('handles');
    const request = store.put(dirHandle, 'outputDir');
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  }});
}}

async function ensureOutputDirHandle() {{
  if (!('showDirectoryPicker' in window) || !('indexedDB' in window)) {{
    return null;
  }}

  if (outputDirHandleCache) {{
    const cachedPermission = await outputDirHandleCache.queryPermission({{ mode: 'readwrite' }});
    if (cachedPermission === 'granted') {{
      return outputDirHandleCache;
    }}
  }}

  let dirHandle = await loadStoredOutputDirHandle();
  if (dirHandle) {{
    const permission = await dirHandle.queryPermission({{ mode: 'readwrite' }});
    if (permission === 'granted') {{
      outputDirHandleCache = dirHandle;
      return dirHandle;
    }}
    if (!DISABLE_DIRECTORY_PICKER && permission === 'prompt') {{
      const requestPermission = await dirHandle.requestPermission({{ mode: 'readwrite' }});
      if (requestPermission === 'granted') {{
        outputDirHandleCache = dirHandle;
        return dirHandle;
      }}
    }}
  }}

  if (DISABLE_DIRECTORY_PICKER) {{
    return null;
  }}

  const pickedDir = await window.showDirectoryPicker({{ mode: 'readwrite' }});
  let targetDir = pickedDir;
  if (pickedDir.name !== 'output') {{
    targetDir = await pickedDir.getDirectoryHandle('output', {{ create: true }});
  }}
  outputDirHandleCache = targetDir;
  await storeOutputDirHandle(targetDir);
  return targetDir;
}}

function downloadTextFile(fileName, content) {{
  const blob = new Blob([content], {{ type: 'application/json;charset=utf-8' }});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}}

async function confirmStatus() {{
  const button = document.getElementById('confirm-status-btn');
  const messageEl = document.getElementById('status-save-message');
  const now = new Date();
  const timestamp = now.toISOString();
  const currentWeek = getIsoWeek(now);
  const rcStatusPayload = buildRcStatusPayload();
  const historyRcStatusPayload = buildHistoryRcStatusPayload(rcStatusPayload);
  const historyPayload = cloneJson(RC_STATUS_HISTORY || {{ tracking_history: [] }});
  if (!Array.isArray(historyPayload.tracking_history)) historyPayload.tracking_history = [];
  historyPayload.tracking_history.push({{
    week: currentWeek,
    date: timestamp,
    user: WINDOWS_USER,
    rc_status: historyRcStatusPayload.rc_status,
  }});

  const rcStatusText = JSON.stringify(rcStatusPayload, null, 2);
  const historyText = JSON.stringify(historyPayload, null, 2);

  button.disabled = true;
  button.style.opacity = '0.7';
  messageEl.textContent = 'Saving status files...';

  try {{
    const targetDir = await ensureOutputDirHandle();
    if (targetDir) {{
      await writeTextFile(targetDir, 'rc_status.json', rcStatusText);
      await writeTextFile(targetDir, 'rc_status_history.json', historyText);
      RC_STATUS_DATA.rc_status = rcStatusPayload.rc_status;
      RC_STATUS_DATA.selected_for_release = rcStatusPayload.selected_for_release;
      RC_STATUS_HISTORY.tracking_history = historyPayload.tracking_history;
      messageEl.textContent = `Saved rc_status.json and rc_status_history.json at ${{timestamp}}.`;
    }} else {{
      downloadTextFile('rc_status.json', rcStatusText);
      downloadTextFile('rc_status_history.json', historyText);
      messageEl.textContent = 'Browser does not allow direct file writes here. Downloaded updated rc_status.json and rc_status_history.json instead.';
    }}
  }} catch (error) {{
    if (error && error.name === 'AbortError') {{
      messageEl.textContent = 'Save cancelled.';
    }} else {{
      downloadTextFile('rc_status.json', rcStatusText);
      downloadTextFile('rc_status_history.json', historyText);
      messageEl.textContent = 'Direct write failed. Downloaded updated rc_status.json and rc_status_history.json instead.';
    }}
  }} finally {{
    button.disabled = false;
    button.style.opacity = '1';
  }}
}}

function ticketSearch(val) {{
  const container = document.getElementById('ticket-search-results');
  const keys = val.split(/[\s,;]+/).map(k => {{
    k = k.trim().toUpperCase();
    if (/^\d+$/.test(k)) k = 'Y3839-' + k;
    else if (/^Y3839-?(\d+)$/.test(k)) k = k.replace(/^Y3839-?/, 'Y3839-');
    return k;
  }}).filter(Boolean);
  if (!keys.length) {{ container.innerHTML = ''; return; }}
  let html = '';
  for (const key of keys) {{
    const hits = TICKET_INDEX[key];
    const bug  = JIRA_BUGS[key];
    if (!hits && !bug) {{
      html += '<div class="ts-result"><div class="ts-not-found">❌ ' + key + ' — not found in any symptom or open bug list</div></div>';
      continue;
    }}
    const entries = hits || [{{symptom:'Not Assigned',rc:'–',status:bug.status,priority:bug.priority,url:bug.url,summary:bug.summary}}];
    const pcol = PRIO_COL[entries[0].priority] || '#444';
    html += '<div class="ts-result">'
      + '<div class="ts-result-header">'
      + '<a href="' + (entries[0].url||'#') + '" target="_blank" style="color:#856404;text-decoration:none">' + key + '</a>'
      + '<span class="ts-badge" style="background:' + pcol + ';color:white">' + (entries[0].priority||'') + '</span>'
      + '<span class="ts-badge">' + (entries[0].status||'') + '</span>'
      + '</div>'
      + '<div style="font-size:0.83em;color:#444;margin-bottom:6px">' + (entries[0].summary||'') + '</div>';
    for (const e of entries) {{
      html += '<div class="ts-result-row">'
        + '<span><span class="ts-label">Symptom:</span> ' + e.symptom + '</span>'
        + '<span><span class="ts-label">Root Cause:</span> ' + e.rc + '</span>'
        + '</div>';
    }}
    html += '</div>';
  }}
  container.innerHTML = html || '<div class="ts-not-found">No results.</div>';
}}

function showBugDetail(key) {{
  const d = JIRA_BUGS[key];
  if (!d) return;
  const col = PRIO_COL[d.priority] || '#444';
  const desc = (d.desc || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\\n/g,'<br>');
  document.getElementById('bug-modal-content').innerHTML =
    '<div style="margin-bottom:14px">'
    + '<a href="'+d.url+'" target="_blank" style="font-size:1.15em;font-weight:700;color:#1a6b8a;text-decoration:none">'+key+'</a>'
    + '<span style="margin-left:10px;background:'+col+';color:white;border-radius:4px;padding:2px 8px;font-size:0.8em">'+d.priority+'</span>'
    + '<span style="margin-left:6px;background:#e2e8f0;border-radius:4px;padding:2px 8px;font-size:0.8em">'+d.status+'</span>'
    + '</div>'
    + '<div style="font-size:1em;font-weight:600;margin-bottom:14px;color:#1a2433;line-height:1.4">'+d.summary+'</div>'
    + '<hr style="border:none;border-top:1px solid #dde3ea;margin:12px 0">'
    + (d.ai_summary ? '<div style="background:#f0f7ff;border-left:3px solid #2980b9;padding:10px 14px;border-radius:0 6px 6px 0;font-size:0.88em;color:#1a2433;line-height:1.6;margin-bottom:12px">' + d.ai_summary + '</div>' : '')
    + '<div style="font-size:0.84em;color:#666;line-height:1.65;max-height:300px;overflow-y:auto">'
    + (desc || '<em style="color:#888">No description available</em>') + '</div>';
  document.getElementById('bug-modal').style.display = 'flex';
}}

function closeBugModal() {{
  document.getElementById('bug-modal').style.display = 'none';
}}

function resetFilters() {{
  document.getElementById('f-region').value='';
  document.getElementById('f-prio').value='';
  document.getElementById('f-cat').value='';
  document.getElementById('cb-complaint').checked=true;
  document.getElementById('cb-inquiry').checked=true;
  document.getElementById('cb-rest').checked=true;
  // Restore original KPI values
  document.getElementById('kpi-total').textContent = nf(TOTAL_ALL);
  applyFilter();
}}

setStatusScope('overall');
resetFilters();
</script>
</body>
</html>"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = round(OUTPUT_PATH.stat().st_size / 1024, 1)
    print(f"  HTML written: {OUTPUT_PATH}  ({size_kb} KB)")
    return str(OUTPUT_PATH)


if __name__ == "__main__":
    run()
