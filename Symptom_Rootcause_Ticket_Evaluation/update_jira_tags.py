import json

# Read the JSON file
with open('output/symptom_analysis_jira.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Define replacements: old text -> new text
replacements = {
    "Loose sensor cable screws [HW]": "Loose sensor cable screws [CM]",
    "Incorrect torque used during sensor cable exchange [HW]": "Incorrect torque used during sensor cable exchange [CM]",
    "More than one USB3 remote connected to acquisition PC [HW]": "More than one USB3 remote connected to acquisition PC [CM]",
    "USB cable physically damaged [HW]": "USB cable physically damaged [CM]",
}

# Function to recursively replace strings in nested structures
def replace_in_object(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = replace_in_object(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = replace_in_object(item)
    elif isinstance(obj, str):
        for old, new in replacements.items():
            obj = obj.replace(old, new)
        return obj
    return obj

# Apply replacements
data = replace_in_object(data)

# Write back
with open('output/symptom_analysis_jira.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Updated all RC tags from [HW] to [CM] for the 4 communication-related causes")
