import json
import re
import pathlib

root = pathlib.Path(r'c:\Users\dirlq523\OneDrive - Dentsply Sirona\_IO-Sensor\10_Qualität\05_Feld\99_Siroforce\00_Git\Y3839-IO_Workspace\Symptom_Rootcause_Ticket_Evaluation')
html_path = root / 'output' / 'Symptom_Trend_Report.html'
history_path = root / 'output' / 'rc_status_history.json'
html = html_path.read_text(encoding='utf-8')
match = re.search(r'const RC_STATUS_DATA = (\{.*?\});\s*const RC_STATUS_HISTORY', html, re.S)
if not match:
    raise SystemExit('RC_STATUS_DATA not found in HTML')
current = json.loads(match.group(1))
hist = json.loads(history_path.read_text(encoding='utf-8'))
updated = False
for entry in hist.get('tracking_history', []):
    if str(entry.get('week', '')).strip() == '2026-W42':
        entry['rc_status'] = current['rc_status']
        updated = True
        break
if not updated:
    raise SystemExit('2026-W42 not found in history')
history_path.write_text(json.dumps(hist, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('updated_history_from_html=2026-W42')
print('sample_root_selected=', current['rc_status']['Intermittent Connectivity']['Loose micro-B USB interface (no cable clip used)']['selected'])
print('sample_ticket_selected=', current['rc_status']['Intermittent Connectivity']['Loose micro-B USB interface (no cable clip used)']['jira_tickets'][0]['selected'])
