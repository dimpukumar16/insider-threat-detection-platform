import os
import sys
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
import pandas as pd

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.detector import build_complete_pipeline

app = Flask(__name__, static_folder="static", static_url_path="")

# Load and process data once on startup (in-memory cache for fast dashboard interactions)
print("Initializing Threat Detection Pipeline...")
results_df, profiles_df, user_baselines = build_complete_pipeline()
print("Pipeline initialization completed successfully!")

# In-memory mock store for analyst actions (persistence during server run)
analyst_actions = {}

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

@app.route("/api/stats", methods=["GET"])
def get_stats():
    # Severity counts
    severity_counts = results_df['severity'].value_counts().to_dict()
    for s in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        severity_counts.setdefault(s, 0)
        
    # Department breakdown
    dept_counts = results_df[results_df['severity'].isin(['CRITICAL', 'HIGH'])].groupby('department').size().to_dict()
    
    # Drift stats
    total_system_drift = int(results_df['system_drift'].sum())
    total_hours_drift = int(results_df['hours_drift'].sum())
    total_stale_access = int(results_df['is_stale'].sum())
    
    # Timeline data for line charts (daily aggregations)
    results_df['date_str'] = pd.to_datetime(results_df['timestamp']).dt.date.astype(str)
    timeline = results_df.groupby('date_str').agg(
        total_events=('risk_score', 'count'),
        high_risk_events=('severity', lambda x: x.isin(['CRITICAL', 'HIGH']).sum())
    ).reset_index().to_dict('records')
    
    # Sort timeline by date
    timeline = sorted(timeline, key=lambda x: x['date_str'])

    return jsonify({
        'total_events': len(results_df),
        'severities': severity_counts,
        'department_alerts': dept_counts,
        'drifts': {
            'system_drift': total_system_drift,
            'hours_drift': total_hours_drift,
            'stale_access': total_stale_access
        },
        'timeline': timeline
    })

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    # Read query parameters for filtering
    severity = request.args.get('severity', '')
    department = request.args.get('department', '')
    search = request.args.get('search', '').lower()
    
    filtered = results_df.copy()
    
    if severity:
        filtered = filtered[filtered['severity'] == severity]
    if department:
        filtered = filtered[filtered['department'] == department]
    if search:
        filtered = filtered[
            filtered['username'].str.lower().str.contains(search) | 
            filtered['resource'].str.lower().str.contains(search) |
            filtered['user_id'].str.lower().str.contains(search)
        ]
        
    # Order by risk score descending
    filtered = filtered.sort_values(by='risk_score', ascending=False)
    
    # Convert to JSON records list
    records = filtered.to_dict('records')
    
    # Enrich with analyst action status
    for r in records:
        r_id = str(r['index'])
        r['action_status'] = analyst_actions.get(r_id, {'state': 'PENDING', 'notes': ''})
        
    return jsonify(records)

@app.route("/api/users", methods=["GET"])
def get_users():
    # Join profiles with their max risk score from results
    max_risks = results_df.groupby('user_id')['risk_score'].max().to_dict()
    alert_counts = results_df[results_df['severity'].isin(['CRITICAL', 'HIGH'])].groupby('user_id').size().to_dict()
    
    users = profiles_df.to_dict('records')
    for u in users:
        uid = u['user_id']
        u['max_risk_score'] = float(max_risks.get(uid, 0.0))
        u['high_risk_alerts_count'] = int(alert_counts.get(uid, 0))
        
        # User baseline stats
        baseline = user_baselines.get(uid, {})
        u['total_logged_accesses'] = int(baseline.get('total_accesses', 0))
        u['avg_daily_queries'] = float(baseline.get('mean_daily', 0.0))
        
    # Sort by risk score descending
    users = sorted(users, key=lambda x: x['max_risk_score'], reverse=True)
    
    return jsonify(users)

@app.route("/api/action", methods=["POST"])
def post_action():
    data = request.json or {}
    alert_id = str(data.get('alert_id'))
    action_type = data.get('action') # "CONTAINED", "DISMISSED", "ESCALATED"
    notes = data.get('notes', '')
    
    if not alert_id:
        return jsonify({'error': 'Missing alert_id'}), 400
        
    analyst_actions[alert_id] = {
        'state': action_type,
        'notes': notes,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return jsonify({'success': True, 'alert_id': alert_id, 'action': action_type})

@app.route("/api/user-timeline", methods=["GET"])
def get_user_timeline():
    user_id = request.args.get('user_id', '')
    before_timestamp = request.args.get('before_timestamp', '')
    
    if not user_id or not before_timestamp:
        return jsonify({'error': 'Missing user_id or before_timestamp'}), 400
        
    try:
        limit_time = pd.to_datetime(before_timestamp)
    except Exception as e:
        return jsonify({'error': f'Invalid timestamp format: {e}'}), 400
        
    # Filter logs of this user preceding or equal to this event's timestamp
    # Using string timestamps comparison or datetime conversion
    results_df['datetime_parsed'] = pd.to_datetime(results_df['timestamp'])
    filtered = results_df[
        (results_df['user_id'] == user_id) & 
        (results_df['datetime_parsed'] <= limit_time)
    ].copy()
    
    # Sort chronologically and take last 5 events
    filtered = filtered.sort_values(by='timestamp', ascending=True)
    last_5 = filtered.tail(5).to_dict('records')
    
    # Remove datetime_parsed for JSON serialization
    for r in last_5:
        r.pop('datetime_parsed', None)
        
    return jsonify(last_5)

if __name__ == "__main__":
    # Start server locally on 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
