#!/usr/bin/env python3
"""
Generate HTML visualization of Status Development per Symptom.
Creates an interactive report with symptom clustering and status distribution charts.
"""

import json
from pathlib import Path
from collections import defaultdict


def normalize_status(status):
    # Handle legacy scalar status as well as current dict-based RC entries.
    if isinstance(status, dict):
        explicit = (status.get("status") or "").strip()
        if explicit:
            status = explicit
        else:
            # Fallback to highest-priority status seen on linked Jira tickets.
            jira_statuses = [
                (t or {}).get("status")
                for t in (status.get("jira_tickets") or [])
                if isinstance(t, dict)
            ]
            priority = ("InAnalysis", "InProgress", "OnHold", "Solved")
            status = next((s for s in priority if s in jira_statuses), "")

    status = (status or "").strip()
    if status == "Completed":
        return "Solved"
    return status

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
    symptom_timeline = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    for entry in history.get("tracking_history", []):
        week = entry["week"]
        rc_status = entry["rc_status"]
        
        for symptom, rcs_dict in rc_status.items():
            if isinstance(rcs_dict, dict):
                for rc_name, status in rcs_dict.items():
                    normalized_status = normalize_status(status)
                    if normalized_status:
                        symptom_timeline[symptom][week][normalized_status] += 1
    
    return symptom_timeline

def generate_html(history):
    """Generate HTML report"""
    
    symptom_timeline = analyze_by_symptom(history)
    
    # Calculate global stats
    latest_entry = history["tracking_history"][-1]
    week = latest_entry["week"]
    
    status_totals = defaultdict(int)
    symptom_stats = []
    
    for symptom, weeks_data in sorted(symptom_timeline.items()):
        latest_week_data = weeks_data[week]
        
        stats = {
            'symptom': symptom,
            'completed': latest_week_data.get('Solved', 0),
            'inprogress': latest_week_data.get('InProgress', 0),
            'inanalysis': latest_week_data.get('InAnalysis', 0),
            'onhold': latest_week_data.get('OnHold', 0),
        }
        stats['total'] = sum([stats['completed'], stats['inprogress'], stats['inanalysis'], stats['onhold']])
        stats['open'] = stats['inanalysis'] + stats['inprogress'] + stats['onhold']
        symptom_stats.append(stats)
        
        for status, count in latest_week_data.items():
            status_totals[status] += count
    
    # Sort by open issues
    symptom_stats.sort(key=lambda x: x['open'], reverse=True)
    
    html = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Development per Symptom</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .kpi-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
        .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }
        .kpi-value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        .kpi-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .kpi-pct {
            font-size: 14px;
            color: #999;
            margin-top: 8px;
        }
        .content {
            padding: 30px;
        }
        .chart-container {
            position: relative;
            height: 300px;
            margin: 30px 0;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h2 {
            color: #333;
            font-size: 20px;
            margin: 30px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        .symptom-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .symptom-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-top: 4px solid #667eea;
        }
        .symptom-title {
            font-size: 15px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
        }
        .status-bar {
            display: flex;
            height: 30px;
            border-radius: 4px;
            overflow: hidden;
            background: #f0f0f0;
            margin-bottom: 10px;
        }
        .status-segment {
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
            transition: opacity 0.3s;
        }
        .status-segment:hover {
            opacity: 0.8;
        }
        .status-completed { background: #10b981; }
        .status-inprogress { background: #3b82f6; }
        .status-inanalysis { background: #f59e0b; }
        .status-onhold { background: #9ca3af; }
        .status-legend {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background: #f0f0f0;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 2px solid #ddd;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        tr:hover {
            background: #f9f9f9;
        }
        .text-right {
            text-align: right;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-completed { background: #d1fae5; color: #065f46; }
        .badge-inprogress { background: #dbeafe; color: #1e40af; }
        .badge-inanalysis { background: #fed7aa; color: #92400e; }
        .badge-onhold { background: #e5e7eb; color: #374151; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Status Development per Symptom</h1>
            <p>Clustered View with Historical Tracking</p>
        </header>
        
        <div class="kpi-section">
"""
    
    # Add KPI cards
    total_rc = sum(stat['total'] for stat in symptom_stats)
    total_completed = status_totals.get('Solved', 0)
    total_open = total_rc - total_completed
    
    html += f"""
            <div class="kpi-card">
                <div class="kpi-label">Total Symptoms</div>
                <div class="kpi-value">{len(symptom_stats)}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total RCs</div>
                <div class="kpi-value">{total_rc}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Solved</div>
                <div class="kpi-value" style="color: #10b981;">{total_completed}</div>
                <div class="kpi-pct">{total_completed/total_rc*100:.1f}% done</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Open Issues</div>
                <div class="kpi-value" style="color: #ef4444;">{total_open}</div>
                <div class="kpi-pct">{total_open/total_rc*100:.1f}% remaining</div>
            </div>
        </div>
        
        <div class="content">
            <h2>📈 Global Status Distribution</h2>
            <div class="status-legend">
                <div class="legend-item">
                    <div class="legend-color status-completed"></div>
                    <span>Solved: {status_totals.get('Solved', 0)}</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color status-inprogress"></div>
                    <span>In Progress: {status_totals.get('InProgress', 0)}</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color status-inanalysis"></div>
                    <span>In Analysis: {status_totals.get('InAnalysis', 0)}</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color status-onhold"></div>
                    <span>On Hold: {status_totals.get('OnHold', 0)}</span>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="globalChart"></canvas>
            </div>
            
            <h2>🔴 Symptoms by Open Issues</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symptom</th>
                        <th class="text-right">Solved</th>
                        <th class="text-right">In Analysis</th>
                        <th class="text-right">In Progress</th>
                        <th class="text-right">On Hold</th>
                        <th class="text-right">Open</th>
                        <th class="text-right">Total</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add symptom rows
    for stat in symptom_stats:
        pct_open = stat['open'] / stat['total'] * 100 if stat['total'] > 0 else 0
        html += f"""
                    <tr>
                        <td><strong>{stat['symptom']}</strong></td>
                        <td class="text-right"><span class="badge badge-completed">{stat['completed']}</span></td>
                        <td class="text-right"><span class="badge badge-inanalysis">{stat['inanalysis']}</span></td>
                        <td class="text-right"><span class="badge badge-inprogress">{stat['inprogress']}</span></td>
                        <td class="text-right"><span class="badge badge-onhold">{stat['onhold']}</span></td>
                        <td class="text-right"><strong style="color: #ef4444;">{stat['open']}</strong></td>
                        <td class="text-right"><strong>{stat['total']}</strong></td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
            
            <h2>📌 Status per Symptom (Visual)</h2>
            <div class="symptom-grid">
"""
    
    # Add symptom cards with status bars
    for stat in symptom_stats:
        html += f"""
                <div class="symptom-card">
                    <div class="symptom-title">{stat['symptom']}</div>
                    <div class="status-bar">
"""
        
        # Add status segments
        for status, color_class in [('completed', 'status-completed'), 
                                      ('inprogress', 'status-inprogress'),
                                      ('inanalysis', 'status-inanalysis'),
                                      ('onhold', 'status-onhold')]:
            count = stat[status]
            if count > 0:
                width = (count / stat['total'] * 100)
                html += f'                        <div class="status-segment {color_class}" style="width: {width}%;" title="{status}: {count}">{count}</div>\n'
        
        html += f"""
                    </div>
                    <div style="font-size: 12px; color: #666; text-align: right;">
                        {stat['open']} open / {stat['total']} total
                    </div>
                </div>
"""
    
    html += f"""
            </div>
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('globalChart').getContext('2d');
        const globalChart = new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: ['Solved', 'In Analysis', 'In Progress', 'On Hold'],
                datasets: [{{
                    data: [
                        {status_totals.get('Solved', 0)},
                        {status_totals.get('InAnalysis', 0)},
                        {status_totals.get('InProgress', 0)},
                        {status_totals.get('OnHold', 0)}
                    ],
                    backgroundColor: [
                        '#10b981',
                        '#f59e0b',
                        '#3b82f6',
                        '#9ca3af'
                    ],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right',
                        labels: {{
                            padding: 20,
                            font: {{ size: 14, weight: 'bold' }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    return html

if __name__ == "__main__":
    history = load_history()
    if history:
        html = generate_html(history)
        
        output_file = Path("output/Status_Development_per_Symptom.html")
        output_file.write_text(html, encoding='utf-8')
        
        print(f"✅ Generated: {output_file.name}")
        print(f"Open in browser: file:///{output_file.absolute()}")
