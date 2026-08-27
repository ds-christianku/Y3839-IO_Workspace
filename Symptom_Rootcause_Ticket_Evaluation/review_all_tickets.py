import json

with open('output/symptom_analysis_jira.json', encoding='utf-8') as f:
    data = json.load(f)
with open('output/jira_summaries.json', encoding='utf-8') as f:
    summaries = json.load(f)

for sym in data['symptoms']:
    tickets_in_sym = sum(len(rc.get('jira_tickets', [])) for rc in sym.get('root_causes_jira', []))
    if tickets_in_sym == 0:
        continue
    print(f"\n{'='*70}")
    print(f"SYMPTOM: {sym['name']}")
    print(f"{'='*70}")
    for rc in sym.get('root_causes_jira', []):
        tickets = rc.get('jira_tickets', [])
        if not tickets:
            continue
        print(f"\n  RC: {rc['text']}")
        for t in tickets:
            key = t['key']
            ai = summaries.get(key, '(keine KI-Zusammenfassung)')
            print(f"    [{t['source']:6s} {t['score']:3d}]  {key}: {t['summary'][:60]}")
            print(f"           AI: {ai[:120]}")
