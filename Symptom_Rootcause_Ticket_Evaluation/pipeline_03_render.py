#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_03_render.py
Renders symptom analysis as a self-contained HTML report with trend charts.
"""

import json
import base64
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
INPUT_PATH = BASE_DIR / "output" / "symptom_analysis.json"
OUTPUT_PATH = BASE_DIR / "output" / "Symptom_Trend_Report.html"


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
    """Replace [HW] and [SW] with colored badges."""
    text = text.replace("[HW]", '<span style="background:#e67e22;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">HW</span>')
    text = text.replace("[SW]", '<span style="background:#2980b9;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">SW</span>')
    return text


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
            rows += f"""
      <tr>
        <td class="symptom-name">{s["name"]}<br>{rc_html}</td>
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
    if jira_path.exists():
        with open(jira_path, encoding="utf-8") as f:
            jira_data = json.load(f)
        jira_sym_map = {s["name"]: s for s in jira_data.get("symptoms", [])}
    else:
        jira_data = {}
        jira_sym_map = {}

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
    jira_assigned_keys: set = set()
    for sym in jira_data.get("symptoms", []):
        for rc in sym.get("root_causes_jira", []):
            for t in rc.get("jira_tickets", []):
                jira_assigned_keys.add(t["key"])
    jira_assigned  = len(jira_assigned_keys)
    jira_unassigned = jira_total_bugs - jira_assigned
    jira_pct = round(jira_assigned / jira_total_bugs * 100) if jira_total_bugs else 0

    # Symptoms and Root Causes section — with Jira ticket links per root cause
    rc_section_rows = ""
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
        rc_rows_html = ""
        for rc in rc_list:
            tickets = jira_by_rc.get(rc, [])
            rc_id = f"rc-{abs(hash(s['name'] + rc)) % 99999}"
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
            rc_rows_html += f'<li style="margin-bottom:4px">{_tag_rc(rc)}{jira_toggle}</li>'
        # Under Construction / Possible Solution cell
        sol = solutions_map.get(s["name"], {})
        sol_status = sol.get("status", "")
        sol_text   = sol.get("solution", "")
        if sol_text:
            badge_color = "#e67e22" if sol_status == "under_construction" else "#27ae60"
            badge_label = "Under Construction" if sol_status == "under_construction" else "Solution Available"
            sol_html = (
                f'<div style="margin-bottom:6px">'
                f'<span style="background:{badge_color};color:white;border-radius:3px;padding:1px 7px;font-size:0.74em;font-weight:600">{badge_label}</span>'
                f'</div>'
                f'<div style="font-size:0.83em;color:#444;line-height:1.5">{sol_text}</div>'
            )
        else:
            sol_html = '<span style="color:#bbb;font-size:0.8em">—</span>'
        rc_section_rows += f"""
        <tr>
          <td><span style="background:{prio_col};color:white;border-radius:4px;padding:2px 8px;font-size:0.82em;font-weight:600">{prio_label}</span></td>
          <td><strong>{s["name"]}</strong><br>{ai_badge}</td>
          <td><ul style="margin:0;padding-left:16px;font-size:0.88em;color:#444">{rc_rows_html}</ul></td>
          <td style="min-width:220px;vertical-align:top">{sol_html}</td>
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
        desc_html = f'<br><span style="font-size:0.82em;color:#555">{item["description"]}</span>' if item.get("description") else ""
        _backlog_rows += (
            f'<tr>'
            f'<td style="padding:8px 10px"><span style="border-radius:4px;padding:2px 8px;font-size:0.8em;font-weight:600;{badge_style}">{badge_label}</span></td>'
            f'<td style="padding:8px 10px"><strong>{item["title"]}</strong>{desc_html}</td>'
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
    #summary h2 {{ font-size: 1.2em; margin-bottom: 16px; color: var(--accent); }}

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
  </style>
</head>
<body>
<header>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:24px">
    <div style="flex:1">
      <h1>Symptom Root Cause — Ticket Trend Evaluation</h1>
      <div class="meta">Generated: {generated} &nbsp;|&nbsp; Source: tickets_raw.json</div>
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
          <th>Trend {y1}\u2192{y2}</th>
        </tr>
      </thead>
      <tbody>{summary_rows}</tbody>
    </table>
  </section>

  <!-- Symptoms and Root Causes -->
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
          <th style="width:240px">Under Construction / Possible Solution</th>
        </tr>
      </thead>
      <tbody>{rc_section_rows}</tbody>
    </table>
  </section>

  <!-- Group Sections -->
  {backlog_section}

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

const JIRA_BUGS = {jira_bugs_js};
const PRIO_COL = {{Urgent:'#c0392b',High:'#e67e22',Medium:'#2980b9',Low:'#7f8c8d',Lowest:'#95a5a6'}};

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
