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
from pathlib import Path
from datetime import datetime

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
    """Replace [HW], [SW], and [FW] with colored badges."""
    text = text.replace("[HW]", '<span style="background:#e67e22;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">HW</span>')
    text = text.replace("[SW]", '<span style="background:#2980b9;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">SW</span>')
    text = text.replace("[FW]", '<span style="background:#2980b9;color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">SW</span>')
    return text


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
            hint_html = f'<div style="font-size:0.8em;color:#e67e22;margin-top:4px;font-style:italic">💡 {hint_escaped}</div>' if hint else ""
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
    for sym in jira_data.get("symptoms", []):
        if sym["name"] == "Intermittent Connectivity":
            for rc in sym.get("root_causes_jira", []):
                count = len(rc.get("jira_tickets", []))
                if count == 0:
                    continue
                label = _re.sub(r"\s*\[(HW|SW|FW)\]", "", rc["text"]).strip()
                if "[HW]" in rc["text"]:
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
    ic_hw_total = sum(ic_hw_counts)
    ic_sw_total = sum(ic_sw_counts)
    # Siroforce tickets for Intermittent Connectivity
    ic_siroforce = next((s["total"] for s in symptoms if s["name"] == "Intermittent Connectivity"), 0)
    # Top 3 root causes by ticket count
    ic_all_rc = sorted(
        [(l, c) for l, c in zip(ic_hw_labels + ic_sw_labels, ic_hw_counts + ic_sw_counts)],
        key=lambda x: -x[1]
    )[:3]
    ic_top3_html = "".join(
        f'<li style="margin-bottom:4px"><span style="font-weight:600;color:{"#e67e22" if (l, c) in list(zip(ic_hw_labels, ic_hw_counts)) else "#2563eb"}">{c} Tickets</span> &ndash; {l} <span style="background:{"#e67e22" if (l, c) in list(zip(ic_hw_labels, ic_hw_counts)) else "#2980b9"};color:white;border-radius:3px;padding:1px 5px;font-size:0.78em;font-weight:700;margin-left:4px">{"HW" if (l, c) in list(zip(ic_hw_labels, ic_hw_counts)) else "SW"}</span></li>'
        for l, c in ic_all_rc
    )

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
        # Add hint if present
        hint = s.get("hint", "")
        hint_html = ""
        if hint:
            hint_html_escaped = hint.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            hint_html = f'<div style="margin-top:6px;padding-top:6px;border-top:1px solid #ddd;font-size:0.82em;color:#e67e22;font-style:italic">&#128161; {hint_html_escaped}</div>'
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
            sol_html = f'<div class="sol-content" style="display:none">{sol_html}</div>'
        else:
            sol_html = '<span style="color:#bbb;font-size:0.8em">—</span>'
        rc_section_rows += f"""
        <tr>
          <td><span style="background:{prio_col};color:white;border-radius:4px;padding:2px 8px;font-size:0.82em;font-weight:600">{prio_label}</span></td>
          <td><strong>{s["name"]}</strong><br>{ai_badge}</td>
          <td><ul style="margin:0;padding-left:16px;font-size:0.88em;color:#444">{rc_rows_html}</ul>{hint_html}</td>
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
          <button id="sol-toggle-btn" onclick="toggleAllSolutions()" title="Show / Hide all solutions" style="margin-left:12px;padding:4px 10px;border:1px solid rgba(255,255,255,0.4);border-radius:4px;background:rgba(255,255,255,0.15);cursor:pointer;font-size:1em;color:white">&#128161;</button>
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
          <div style="margin-top:4px;color:#888;font-size:0.95em">of which IC: <strong>{ic_hw_total + ic_sw_total}</strong></div>
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
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#e67e22;border-radius:2px;margin-right:3px"></span>HW</span>
          <span style="margin-right:12px"><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:3px"></span>SW</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#94a3b8;border-radius:2px;margin-right:3px"></span>Other Symptoms</span>
        </div>
        <div style="margin-top:12px;font-size:0.82em;color:#555">
          <div style="display:flex;gap:16px;flex-wrap:wrap">
            <span>HW: <strong>{ic_hw_total}</strong></span>
            <span>SW: <strong>{ic_sw_total}</strong></span>
            <span>Other Symptoms: <strong>{jira_assigned - ic_hw_total - ic_sw_total}</strong></span>
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
          <th id="sol-col-header" style="width:240px;cursor:pointer;user-select:none" title="Click &#128161; in a row to reveal solutions">&#128274; Solutions</th>
        </tr>
      </thead>
      <tbody>{rc_section_rows}</tbody>
    </table>
  </section>

  <!-- Group Sections -->
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

  // Chart 3: Intermittent Connectivity HW vs SW vs other assigned tickets
  const ctx3 = document.getElementById('chart3').getContext('2d');
  new Chart(ctx3, {{
    type: 'doughnut',
    data: {{
      labels: ['HW', 'SW', 'Other Symptoms'],
      datasets: [{{
        data: [{ic_hw_total}, {ic_sw_total}, {jira_assigned - ic_hw_total - ic_sw_total}],
        backgroundColor: ['#e67e22', '#2563eb', '#94a3b8'],
        borderColor: ['#d35400', '#1e40af', '#64748b'],
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

const JIRA_BUGS = {jira_bugs_js};
const TICKET_INDEX = {ticket_index_js};
const PRIO_COL = {{Urgent:'#c0392b',High:'#e67e22',Medium:'#2980b9',Low:'#7f8c8d',Lowest:'#95a5a6'}};

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

function revealSolution(lampEl) {{
  const row = lampEl.closest('tr');
  const solDiv = row ? row.querySelector('.sol-content') : null;
  if (solDiv) {{
    const visible = solDiv.style.display !== 'none';
    solDiv.style.display = visible ? 'none' : 'block';
    lampEl.innerHTML = visible ? '&#128161;' : '&#128262;';
    lampEl.style.filter = visible ? '' : 'drop-shadow(0 0 4px #f59e0b)';
  }}
}}

let _solVisible = false;
function toggleAllSolutions() {{
  _solVisible = !_solVisible;
  document.querySelectorAll('.sol-content').forEach(d => d.style.display = _solVisible ? 'block' : 'none');
  const btn = document.getElementById('sol-toggle-btn');
  if (btn) btn.style.background = _solVisible ? 'rgba(255,220,50,0.35)' : 'rgba(255,255,255,0.15)';
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
