#!/usr/bin/env python3
"""
View Status Development per Symptom from tracking history.
Clustered by symptom with status distribution over time.
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def normalize_status(status):
    if status == "Completed":
        return "Solved"
    return status or ""

def load_history():
    """Load rc_status_history.json"""
    history_file = Path("output/rc_status_history.json")
    if not history_file.exists():
        print("❌ rc_status_history.json not found")
        return None
    
    with open(history_file) as f:
        return json.load(f)

def analyze_by_symptom(history):
    """Analyze status distribution per symptom over time"""
    
    # Structure: {symptom: {week: {status: count, ...}}}
    symptom_timeline = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    for entry in history.get("tracking_history", []):
        week = entry["week"]
        date = entry["date"]
        rc_status = entry["rc_status"]
        
        # Iterate through symptoms and their RCs
        for symptom, rcs_dict in rc_status.items():
            if isinstance(rcs_dict, dict):
                for rc_name, status in rcs_dict.items():
                    normalized_status = normalize_status(status)
                    if normalized_status:
                        symptom_timeline[symptom][week][normalized_status] += 1
    
    return symptom_timeline

def print_symptom_timeline(symptom_timeline):
    """Print status development per symptom"""
    
    print("\n" + "="*120)
    print("📊 STATUS DEVELOPMENT PER SYMPTOM (Geclustert)")
    print("="*120)
    
    # Status colors for display
    status_colors = {
        "Solved": "✅",
        "InProgress": "🔄",
        "InAnalysis": "🔍",
        "OnHold": "⏸️"
    }
    
    for symptom in sorted(symptom_timeline.keys()):
        weeks_data = symptom_timeline[symptom]
        
        print(f"\n📌 {symptom}")
        print("-" * 100)
        
        # Print header with weeks
        weeks = sorted(weeks_data.keys())
        header = "Status".ljust(15)
        for week in weeks:
            header += f" | {week}"
        print(header)
        print("-" * 100)
        
        # Get all statuses across all weeks
        all_statuses = set()
        for week_data in weeks_data.values():
            all_statuses.update(week_data.keys())
        
        # Print each status row
        for status in sorted(all_statuses):
            row = f"{status_colors.get(status, '•')} {status}".ljust(15)
            for week in weeks:
                count = weeks_data[week].get(status, 0)
                row += f" | {count:>4}"
            print(row)
        
        # Print total per week
        print("-" * 100)
        total_row = "TOTAL".ljust(15)
        for week in weeks:
            total = sum(weeks_data[week].values())
            total_row += f" | {total:>4}"
        print(total_row)

def print_summary_stats(symptom_timeline):
    """Print summary statistics"""
    
    print("\n" + "="*120)
    print("📈 SUMMARY STATISTICS")
    print("="*120)
    
    total_symptoms = len(symptom_timeline)
    total_rcs = 0
    status_totals = defaultdict(int)
    
    for symptom, weeks_data in symptom_timeline.items():
        # Get latest week
        latest_week = sorted(weeks_data.keys())[-1]
        week_statuses = weeks_data[latest_week]
        
        for status, count in week_statuses.items():
            status_totals[status] += count
            total_rcs += count
    
    print(f"\n🎯 Total Symptoms: {total_symptoms}")
    print(f"📋 Total RCs: {total_rcs}")
    print(f"\nStatus Distribution (Latest Week):")
    print("-" * 50)
    
    for status in ["Solved", "InProgress", "InAnalysis", "OnHold"]:
        count = status_totals.get(status, 0)
        percentage = (count / total_rcs * 100) if total_rcs > 0 else 0
        bar = "█" * int(percentage / 2)
        print(f"  {status:<15} {count:>3} ({percentage:>5.1f}%) {bar}")

def print_symptoms_with_most_issues():
    """Print symptoms sorted by number of open issues"""
    
    print("\n" + "="*120)
    print("🔴 SYMPTOMS BY NUMBER OF OPEN ISSUES (InAnalysis + InProgress + OnHold)")
    print("="*120)
    
    history = load_history()
    if not history:
        return
    
    latest_entry = history["tracking_history"][-1]
    rc_status = latest_entry["rc_status"]
    
    symptom_issues = []
    
    for symptom, rcs_dict in rc_status.items():
        if isinstance(rcs_dict, dict):
            normalized_statuses = [normalize_status(status) for status in rcs_dict.values()]
            open_issues = sum(1 for status in normalized_statuses
                            if status in ["InAnalysis", "InProgress", "OnHold"])
            total = len(rcs_dict)
            completed = sum(1 for status in normalized_statuses if status == "Solved")
            symptom_issues.append({
                'symptom': symptom,
                'open': open_issues,
                'completed': completed,
                'total': total
            })
    
    # Sort by open issues descending
    symptom_issues.sort(key=lambda x: x['open'], reverse=True)
    
    print(f"\n{'Symptom':<45} {'Open':<8} {'Completed':<12} {'Total':<8}")
    print("-" * 100)
    
    for item in symptom_issues:
        pct_open = (item['open'] / item['total'] * 100) if item['total'] > 0 else 0
        pct_comp = (item['completed'] / item['total'] * 100) if item['total'] > 0 else 0
        print(f"{item['symptom']:<45} {item['open']:<8} {item['completed']:<12} {item['total']:<8} "
              f"({pct_open:>5.1f}% open, {pct_comp:>5.1f}% done)")

if __name__ == "__main__":
    history = load_history()
    if history:
        symptom_timeline = analyze_by_symptom(history)
        print_symptom_timeline(symptom_timeline)
        print_summary_stats(symptom_timeline)
        print_symptoms_with_most_issues()
        
        # Print latest timestamp
        latest_entry = history["tracking_history"][-1]
        print(f"\n⏰ Latest Update: {latest_entry['date']}")
