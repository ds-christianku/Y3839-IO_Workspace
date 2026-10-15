#!/usr/bin/env python3
"""
Script to display status history and changes over time.
Shows when RCs changed status and which ones are progressing.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent


def normalize_status(status):
    if status == "Completed":
        return "Solved"
    return status or ""

def main():
    history_path = BASE_DIR / "output" / "rc_status_history.json"
    
    if not history_path.exists():
        print("❌ Error: rc_status_history.json not found")
        sys.exit(1)
    
    with open(history_path, 'r', encoding='utf-8') as f:
        history_data = json.load(f)
    
    tracking_history = history_data.get("tracking_history", [])
    
    if not tracking_history:
        print("📊 No tracking history found")
        return
    
    print(f"\n{'='*80}")
    print(f"Status History - {len(tracking_history)} Snapshots")
    print(f"{'='*80}\n")
    
    # Show all snapshots
    for i, entry in enumerate(tracking_history, 1):
        week = entry.get("week", "Unknown")
        date = entry.get("date", "")
        status_counts = defaultdict(int)
        
        rc_status = entry.get("rc_status", {})
        # Flatten hierarchical structure: symptom -> rc -> status
        all_statuses = []
        for symptom, rcs_dict in rc_status.items():
            if isinstance(rcs_dict, dict):
                for rc, status in rcs_dict.items():
                    normalized_status = normalize_status(status)
                    if not normalized_status:
                        continue
                    status_counts[normalized_status] += 1
                    all_statuses.append((rc, normalized_status))
        
        print(f"📅 Snapshot {i}: Week {week} ({date[:10]})")
        print(f"   OnHold: {status_counts.get('OnHold', 0)}, " +
              f"InAnalysis: {status_counts.get('InAnalysis', 0)}, " +
              f"InProgress: {status_counts.get('InProgress', 0)}, " +
              f"Solved: {status_counts.get('Solved', 0)}")
        
        # Show detailed status if requested
        if len(tracking_history) > 1 and i < len(tracking_history):
            print(f"   Changes compared to previous week:")
            prev_status_flat = {}
            prev_rc_status = tracking_history[i-1].get("rc_status", {})
            for symptom, rcs_dict in prev_rc_status.items():
                if isinstance(rcs_dict, dict):
                    for rc, status in rcs_dict.items():
                        prev_status_flat[rc] = normalize_status(status)
            
            for rc, status in all_statuses:
                prev_st = prev_status_flat.get(rc, "Unknown")
                if status != prev_st:
                    print(f"   • {rc[:60]}...")
                    print(f"     {prev_st} → {status}")
        print()
    
    # Summary statistics
    latest = tracking_history[-1].get("rc_status", {})
    latest_statuses = []
    for symptom, rcs_dict in latest.items():
        if isinstance(rcs_dict, dict):
            for status in rcs_dict.values():
                normalized_status = normalize_status(status)
                if normalized_status:
                    latest_statuses.append(normalized_status)
    print(f"{'='*80}")
    print(f"Latest Status Summary (Week {tracking_history[-1].get('week')})")
    print(f"{'='*80}")
    
    for status in ["OnHold", "InAnalysis", "InProgress", "Solved"]:
        count = sum(1 for s in latest_statuses if s == status)
        pct = (count / len(latest_statuses) * 100) if latest_statuses else 0
        print(f"{status:15} {count:3} ({pct:5.1f}%)")

if __name__ == "__main__":
    main()
