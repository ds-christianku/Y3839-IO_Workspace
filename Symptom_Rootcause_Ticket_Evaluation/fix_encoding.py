import json

# Read UTF-16 file and convert to UTF-8
with open('output/symptom_analysis_jira.json', 'r', encoding='utf-16') as f:
    data = json.load(f)

# Write back as UTF-8
with open('output/symptom_analysis_jira.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Converted to UTF-8')
