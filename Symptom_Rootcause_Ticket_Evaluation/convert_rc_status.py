#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert rc_status.json from flat structure to hierarchical (symptom -> rc -> status)
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RC_STATUS_PATH = BASE_DIR / "output" / "rc_status.json"
SYMPTOM_ANALYSIS_PATH = BASE_DIR / "output" / "symptom_analysis.json"

# Load current rc_status.json
with open(RC_STATUS_PATH, encoding="utf-8") as f:
    old_data = json.load(f)

# Load symptom_analysis.json to get symptom -> rc mapping
with open(SYMPTOM_ANALYSIS_PATH, encoding="utf-8") as f:
    symptoms_data = json.load(f)

# Build new hierarchical structure
new_rc_status = {}

for symptom in symptoms_data.get("symptoms", []):
    symptom_name = symptom.get("name")
    root_causes = symptom.get("root_causes", [])
    
    new_rc_status[symptom_name] = {}
    
    for rc in root_causes:
        # Get status from old structure, default to "OnHold"
        status = old_data.get("rc_status", {}).get(rc, "OnHold")
        new_rc_status[symptom_name][rc] = status

# Write new structure
with open(RC_STATUS_PATH, "w", encoding="utf-8") as f:
    json.dump({"rc_status": new_rc_status}, f, indent=2, ensure_ascii=False)

print(f"✅ Converted rc_status.json to hierarchical structure")
print(f"📊 {len(new_rc_status)} symptoms with root causes")
