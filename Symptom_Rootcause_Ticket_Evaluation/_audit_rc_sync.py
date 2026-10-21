import json, re, pathlib
root = pathlib.Path(r'c:\Users\dirlq523\OneDrive - Dentsply Sirona\_IO-Sensor\10_Qualität\05_Feld\99_Siroforce\00_Git\Y3839-IO_Workspace\Symptom_Rootcause_Ticket_Evaluation')
hist = json.loads((root/'output'/'rc_status_history.json').read_text(encoding='utf-8'))
latest = hist['tracking_history'][-1]['rc_status']
html = (root/'output'/'Symptom_Trend_Report.html').read_text(encoding='utf-8')
match = re.search(r'const RC_STATUS_DATA = (\{.*?\})(?=\s*const (?:RELEASE_RC_KEYS|RC_STATUS_HISTORY|JIRA_RC_FLAGS|JIRA_RC_STATUSES|JIRA_RC_TICKETS|PRIO_COL))', html, re.S)
print('match_found=', bool(match))
if not match:
    raise SystemExit('RC_STATUS_DATA block not found')
current = json.loads(match.group(1))
mismatches = []
for symptom, rc_map in latest.items():
    html_map = current.get('rc_status', {}).get(symptom, {}) if isinstance(current.get('rc_status'), dict) else {}
    for rc_name, rc_entry in rc_map.items():
        if not isinstance(rc_entry, dict):
            continue
        html_entry = html_map.get(rc_name) if isinstance(html_map, dict) else None
        if html_entry is None:
            mismatches.append((symptom, rc_name, 'missing_in_html', rc_entry.get('selected'), None))
            continue
        for field in ['selected', 'status', 'action_type']:
            if str(html_entry.get(field, '')) != str(rc_entry.get(field, '')):
                mismatches.append((symptom, rc_name, field, rc_entry.get(field), html_entry.get(field)))
        if isinstance(rc_entry.get('jira_tickets'), list):
            html_tickets = html_entry.get('jira_tickets', []) if isinstance(html_entry, dict) else []
            if len(html_tickets) != len(rc_entry['jira_tickets']):
                mismatches.append((symptom, rc_name, 'ticket_count', len(rc_entry['jira_tickets']), len(html_tickets)))
            else:
                for i, ticket in enumerate(rc_entry['jira_tickets']):
                    h = html_tickets[i]
                    if str(h.get('selected', '')) != str(ticket.get('selected', '')):
                        mismatches.append((symptom, rc_name, 'ticket_selected', ticket.get('key', ''), (i, h.get('selected'), ticket.get('selected'))))
print('mismatch_count=', len(mismatches))
for item in mismatches[:20]:
    print(item)
