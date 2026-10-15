#!/usr/bin/env python3
"""
Script to track status changes on a weekly basis.
Run this script weekly to save the current status snapshot to the history.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent

def get_current_week():
    """Get the current ISO week (e.g., '2026-W35')"""
    today = datetime.now()
    return today.strftime("%Y-W%V")

def main():
    rc_status_path = BASE_DIR / "output" / "rc_status.json"
    history_path = BASE_DIR / "output" / "rc_status_history.json"
    
    # Load current status
    if not rc_status_path.exists():
        print("❌ Error: rc_status.json not found")
        sys.exit(1)
    
    with open(rc_status_path, 'r', encoding='utf-8') as f:
        current_data = json.load(f)
    
    current_status = current_data.get("rc_status", {})
    current_week = get_current_week()
    
    # Load history
    if history_path.exists():
        with open(history_path, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
    else:
        history_data = {"tracking_history": []}
    
    tracking_history = history_data.get("tracking_history", [])
    
    # Check if this week already exists
    existing_week = next((h for h in tracking_history if h.get("week") == current_week), None)
    
    if existing_week:
        # Update existing week entry
        existing_week["date"] = datetime.now().isoformat()
        existing_week["rc_status"] = current_status
        print(f"✅ Updated tracking for week {current_week}")
    else:
        # Add new week entry
        new_entry = {
            "week": current_week,
            "date": datetime.now().isoformat(),
            "rc_status": current_status
        }
        tracking_history.append(new_entry)
        print(f"✅ Created new tracking entry for week {current_week}")
    
    # Save updated history
    history_data["tracking_history"] = tracking_history
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)
    
    print(f"📊 Total tracking entries: {len(tracking_history)}")
    print(f"📁 History saved to: {history_path}")

if __name__ == "__main__":
    main()
