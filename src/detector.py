import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Predefined systems mapping list (mapping resources in logs to systems_access in profiles)
RESOURCE_TO_SYSTEM = {
    'PROD_DB': ['PROD_DB', 'ADMIN_SYS'],
    'Admin_Console': ['ADMIN_SYS'],
    'GL_System': ['ADMIN_SYS', 'PROD_DB'],
    'SIEM': ['SIEM'],
    'File_Share': ['AD', 'EMAIL', 'GCP', 'AWS_IAM'],
    'Email_Archive': ['EMAIL'],
    'Customer_Vault': ['PROD_DB', 'Salesforce'],
    'HRIS': ['ServiceNow', 'Azure_AD'],
    'BI_Tool': ['Salesforce', 'ServiceNow', 'EMAIL'],
    'Data_Lake': ['GCP', 'AWS_IAM', 'PROD_DB']
}

def load_data(data_dir=None):
    """
    Loads raw CSV data and returns log and profile dataframes.
    Handles dynamic path resolving for flexibility.
    """
    if data_dir is None:
        # Resolve path relative to the root directory of this project
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.abspath(os.path.join(current_dir, "..", "Problem_04_Data_Access", "sample_data"))
    
    logs_path = os.path.join(data_dir, "data_access_logs.csv")
    profiles_path = os.path.join(data_dir, "user_profiles.csv")
    
    if not os.path.exists(logs_path):
        raise FileNotFoundError(f"Logs file not found at {logs_path}")
    if not os.path.exists(profiles_path):
        raise FileNotFoundError(f"Profiles file not found at {profiles_path}")
        
    logs = pd.read_csv(logs_path)
    profiles = pd.read_csv(profiles_path)
    
    # Parse timestamps
    logs['timestamp'] = pd.to_datetime(logs['timestamp'])
    
    return logs, profiles

def enrich_data(logs, profiles):
    """
    [1] Data Ingestion & Enrichment Layer
    Merges log data with user profiles and extracts initial temporal features.
    """
    # Merge logs and profiles
    enriched = pd.merge(
        logs,
        profiles,
        on="user_id",
        how="left",
        suffixes=('', '_profile')
    )
    
    # Fill missing values for users not found in profiles (orphan account logins)
    enriched['is_active'] = enriched['is_active'].fillna(False)
    enriched['days_inactive'] = enriched['days_inactive'].fillna(999).astype(int)
    enriched['privilege_level'] = enriched['privilege_level'].fillna('user')
    enriched['systems_access'] = enriched['systems_access'].fillna('')
    enriched['department'] = enriched['department'].fillna('unknown')
    enriched['job_title'] = enriched['job_title'].fillna('unknown')
    
    # Extract temporal properties
    enriched['hour'] = enriched['timestamp'].dt.hour
    enriched['day_of_week'] = enriched['timestamp'].dt.dayofweek
    enriched['date'] = enriched['timestamp'].dt.date
    
    return enriched

def build_behavioral_profiles(enriched_logs):
    """
    [2] Behavioral Profiling Engine
    Builds global baseline profiles for users, department, and peer groups.
    """
    user_baselines = {}
    dept_baselines = {}
    peer_baselines = {}
    
    # 1. Compute individual user baselines for overall profiles
    for user_id, group in enriched_logs.groupby('user_id'):
        total_accesses = len(group)
        hour_counts = group['hour'].value_counts()
        hourly_profile = (hour_counts / total_accesses).to_dict()
        time_class_counts = group['time_classification'].value_counts()
        time_affinity = (time_class_counts / total_accesses).to_dict()
        historical_resources = set(group['resource'].dropna().unique())
        historical_actions = set(group['action'].dropna().unique())
        daily_counts = group.groupby('date').size()
        mean_daily = daily_counts.mean()
        std_daily = daily_counts.std() if len(daily_counts) > 1 else 0.0
        
        user_baselines[user_id] = {
            'total_accesses': total_accesses,
            'hourly_profile': hourly_profile,
            'time_affinity': time_affinity,
            'historical_resources': historical_resources,
            'historical_actions': historical_actions,
            'mean_daily': mean_daily,
            'std_daily': std_daily,
            'active_days': len(daily_counts)
        }
        
    # 2. Compute department baseline profiles (fallback for low-data users)
    for dept, group in enriched_logs.groupby('department'):
        total_accesses = len(group)
        time_class_counts = group['time_classification'].value_counts()
        time_affinity = (time_class_counts / total_accesses).to_dict()
        historical_resources = set(group['resource'].dropna().unique())
        historical_actions = set(group['action'].dropna().unique())
        
        dept_baselines[dept] = {
            'time_affinity': time_affinity,
            'historical_resources': historical_resources,
            'historical_actions': historical_actions
        }
        
    # 3. Compute Peer Group Baselines (grouped by department + job_title)
    for (dept, job), group in enriched_logs.groupby(['department', 'job_title']):
        total_actions = len(group)
        user_count = group['user_id'].nunique()
        
        queries_per_user = total_actions / user_count if user_count > 0 else 0
        peer_resources = set(group['resource'].dropna().unique())
        peer_actions = set(group['action'].dropna().unique())
        
        time_class_counts = group['time_classification'].value_counts()
        peer_time_affinity = (time_class_counts / total_actions).to_dict()
        
        peer_baselines[(dept, job)] = {
            'queries_per_user': queries_per_user,
            'peer_resources': peer_resources,
            'peer_actions': peer_actions,
            'peer_time_affinity': peer_time_affinity
        }
        
    return user_baselines, dept_baselines, peer_baselines


def check_resource_authorization(resource, systems_access_str):
    """
    Helper to check if a user is authorized for a specific resource based on systems_access.
    """
    if not systems_access_str:
        return False
        
    user_systems = [s.strip().upper() for s in systems_access_str.split('|')]
    
    mapped_systems = RESOURCE_TO_SYSTEM.get(resource, [])
    if not mapped_systems:
        # If no explicit mapping, fallback to checking substring match
        return any(system in resource.upper() for system in user_systems)
        
    return any(system.upper() in user_systems for system in mapped_systems)

def calculate_drift_score(row, baseline):
    """
    [3.1] Behavioral Drift Score
    Calculates numerical drift score based on hour deviation, resource drift, and action drift.
    """
    drift = 0
    if baseline:
        # 1. Hour Deviation (Time Drift)
        expected_affinity = baseline['time_affinity'].get(row['time_classification'], 0)
        drift += (1 - expected_affinity) * 45
        
        # 2. Resource Drift (First time accessing system)
        if row['resource'] not in baseline.get('historical_resources', set()):
            drift += 35
            
        # 3. Action/Method Drift (First time using this action method)
        if row['action'] not in baseline.get('historical_actions', set()):
            drift += 20
    else:
        # Fallback for new accounts
        drift = 45
        
    return min(int(drift), 100)

def calculate_peer_deviation(row, peer_baseline):
    """
    [3.2] Peer Group Deviation
    Determines how much a user's action deviates from their peer department+job role baseline.
    """
    deviation = 0
    if peer_baseline:
        # 1. Time deviation compared to peer schedule
        peer_time_affinity = peer_baseline['peer_time_affinity'].get(row['time_classification'], 0)
        deviation += (1 - peer_time_affinity) * 40
        
        # 2. Target system compared to peer baseline system footprint
        if row['resource'] not in peer_baseline.get('peer_resources', set()):
            deviation += 35
            
        # 3. Action method compared to peer baseline action footprint
        if row['action'] not in peer_baseline.get('peer_actions', set()):
            deviation += 25
    else:
        # Default fallback
        deviation = 20
        
    return min(int(deviation), 100)

def check_kill_chains(enriched_logs):
    """
    [3.3] Expanded Kill Chain / Sequence Detection
    Scans for three advanced sequence paths:
    1. BRUTE_FORCE_EXPLOIT: failed logins -> successful login -> high sensitivity access
    2. DRIFT_EXFILTRATION: system drift -> high sensitivity access -> export
    3. OFFHOURS_EXFILTRATION: night access -> high sensitivity -> export
    """
    brute_force_set = set()
    drift_exfil_set = set()
    offhours_exfil_set = set()
    
    sorted_logs = enriched_logs.sort_values(['user_id', 'timestamp']).copy()
    
    for user_id, group in sorted_logs.groupby('user_id'):
        if len(group) < 2:
            continue
            
        group_records = group.to_dict('records')
        
        # Track historical resources visited dynamically to identify drift
        historical_resources = set()
        
        for i in range(len(group_records)):
            current = group_records[i]
            timestamp = current['timestamp']
            resource = current['resource']
            sensitivity = current['resource_sensitivity']
            action = current['action']
            time_class = current['time_classification']
            
            is_new_resource = resource not in historical_resources
            historical_resources.add(resource)
            
            # --- Sequence 1: Brute Force Exploit ---
            if sensitivity == 'high' and i >= 2:
                # Lookback 15 minutes for sequential failures
                time_limit = timestamp - timedelta(minutes=15)
                login_success_found = False
                failures_count = 0
                
                for idx in range(i - 1, -1, -1):
                    prev = group_records[idx]
                    if prev['timestamp'] < time_limit:
                        break
                    if prev['action'] == 'login':
                        if prev['status'] == 'success':
                            login_success_found = True
                        elif prev['status'] == 'failure':
                            failures_count += 1
                
                if login_success_found and failures_count >= 2:
                    brute_force_set.add(group.index[i])
            
            # --- Sequence 2: Drift Exfiltration Chain ---
            if is_new_resource and sensitivity == 'high' and action == 'export_data':
                drift_exfil_set.add(group.index[i])
            elif action == 'export_data' and i > 0:
                time_limit = timestamp - timedelta(minutes=30)
                for idx in range(i - 1, -1, -1):
                    prev = group_records[idx]
                    if prev['timestamp'] < time_limit:
                        break
                    # If they previously logged a new high-sensitivity access
                    prev_is_new = prev['resource'] not in [r['resource'] for r in group_records[:idx]]
                    if prev_is_new and prev['resource_sensitivity'] == 'high':
                        drift_exfil_set.add(group.index[i])
                        break
            
            # --- Sequence 3: Offhours Exfiltration Cycle ---
            if time_class in ['night', 'unusual_hours'] and sensitivity == 'high' and action == 'export_data':
                offhours_exfil_set.add(group.index[i])
                
    return brute_force_set, drift_exfil_set, offhours_exfil_set

def detect_threats_and_score(enriched_logs, dept_baselines, peer_baselines):
    """
    [3] Multi-Layer Threat Detection Engine
    [4] Risk Scoring & Prioritization Engine (Weighted Improvements)
    """
    results = []
    
    # Calculate expanded sequence rules
    bf_chain, de_chain, oe_chain = check_kill_chains(enriched_logs)
    
    # Sort chronologically for dynamic chronological baseline calculations
    df_sorted = enriched_logs.sort_values('timestamp').copy()
    
    # Pre-build chronological indexing structures per user to optimize run speeds
    user_groups = {uid: grp for uid, grp in df_sorted.groupby('user_id')}
    
    for idx, row in df_sorted.iterrows():
        user_id = row['user_id']
        username = row['username']
        resource = row['resource']
        status = row['status']
        action = row['action']
        time_class = row['time_classification']
        sensitivity = row['resource_sensitivity']
        systems_access = row['systems_access']
        is_active = row['is_active']
        days_inactive = row['days_inactive']
        department = row['department']
        job_title = row['job_title']
        
        triggered_rules = []
        drift_signals = []
        
        # --- 1. RULE-BASED DETECTORS (High-Precision) ---
        rule_base_score = 10.0
        
        # A. Stale Account Access
        is_stale = False
        if not is_active:
            triggered_rules.append("STALE_ACCOUNT_ACCESS (Inactive User Profile)")
            rule_base_score = max(rule_base_score, 95)
            is_stale = True
        elif days_inactive > 30:
            triggered_rules.append(f"STALE_ACCOUNT_ACCESS (Account Inactive {days_inactive} Days)")
            if action == 'export_data' and sensitivity == 'high':
                rule_base_score = max(rule_base_score, 95)  # Real exfiltration threat
            elif sensitivity == 'high' and time_class in ['night', 'unusual_hours', 'weekend']:
                rule_base_score = max(rule_base_score, 78)  # High risk combo
            elif sensitivity == 'high' or action == 'export_data':
                rule_base_score = max(rule_base_score, 62)  # Elevated
            else:
                rule_base_score = max(rule_base_score, 35)  # Just monitor - business hours normal
            is_stale = True
            
        # B. Privilege Violation
        if row['privilege_level'] == 'user' and (resource == 'Admin_Console' or action == 'admin_operation'):
            triggered_rules.append("PRIVILEGE_VIOLATION (Unauthorized Admin Task)")
            rule_base_score = max(rule_base_score, 80)
            
        # C. High-Sensitivity Off-Hours Access
        if sensitivity == 'high' and time_class in ['night', 'unusual_hours']:
            triggered_rules.append(f"HIGH_SENSITIVITY_OFF_HOURS (Access to {resource} during {time_class})")
            if row['privilege_level'] == 'admin':
                rule_base_score = max(rule_base_score, 42)  # Admins work late — not critical
            else:
                rule_base_score = max(rule_base_score, 75)  # Regular user — HIGH risk
            
        # D. Access Method Drift / Unauthorized resource access
        is_authorized = check_resource_authorization(resource, systems_access)
        if not is_authorized and systems_access:
            triggered_rules.append(f"UNAUTHORIZED_SYSTEM_ACCESS (Resource {resource} not approved)")
            rule_base_score = max(rule_base_score, 65)
            
        # --- 2. CALCULATE BEHAVIORAL DRIFT DYNAMICALLY (To prevent data leakage) ---
        # Fetch only user logs occurring BEFORE this event
        user_grp = user_groups.get(user_id)
        prior_logs = user_grp[user_grp['timestamp'] < row['timestamp']] if user_grp is not None else pd.DataFrame()
        
        user_baseline = None
        if len(prior_logs) >= 3:
            total_accesses = len(prior_logs)
            time_affinity = (prior_logs['time_classification'].value_counts() / total_accesses).to_dict()
            historical_resources = set(prior_logs['resource'].dropna().unique())
            historical_actions = set(prior_logs['action'].dropna().unique())
            
            # Daily queries baseline
            daily_counts = prior_logs.groupby('date').size()
            mean_daily = daily_counts.mean()
            std_daily = daily_counts.std() if len(daily_counts) > 1 else 0.0
            
            user_baseline = {
                'time_affinity': time_affinity,
                'historical_resources': historical_resources,
                'historical_actions': historical_actions,
                'mean_daily': mean_daily,
                'std_daily': std_daily,
                'active_days': len(daily_counts)
            }
            
        peer_baseline = peer_baselines.get((department, job_title))
        
        drift_score = calculate_drift_score(row, user_baseline)
        peer_deviation = calculate_peer_deviation(row, peer_baseline)
        
        system_drift = False
        hours_drift = False
        if user_baseline:
            if resource not in user_baseline['historical_resources']:
                system_drift = True
                drift_signals.append(f"SYSTEM_DRIFT (First time accessing {resource})")
            expected_affinity = user_baseline['time_affinity'].get(time_class, 0.0)
            if expected_affinity < 0.10:
                hours_drift = True
                drift_signals.append(f"TIME_DRIFT (Rare timing bucket: {time_class})")
        else:
            # Fallback to department baselines if no user baseline yet
            dept_baseline = dept_baselines.get(department)
            if dept_baseline:
                if resource not in dept_baseline['historical_resources']:
                    system_drift = True
                    drift_signals.append(f"SYSTEM_DRIFT_DEPARTMENT (Accessing resource atypical for {department})")
                expected_affinity = dept_baseline['time_affinity'].get(time_class, 0.0)
                if expected_affinity < 0.10:
                    hours_drift = True
                    drift_signals.append(f"TIME_DRIFT_DEPARTMENT (Access time classification atypical for {department})")

        # --- 3. SENSITIVITY & VOLUME SCORE ---
        sens_score = 30.0
        if sensitivity == 'high':
            sens_score = 90.0
        elif sensitivity == 'medium':
            sens_score = 60.0
            
        action_modifier = 0.4
        if action == 'export_data':
            action_modifier = 1.0
        elif action == 'admin_operation':
            action_modifier = 0.8
        elif action in ['sql_query', 'file_access', 'api_call']:
            action_modifier = 0.6
            
        sensitivity_volume = sens_score * action_modifier
        
        # --- 4. KILL CHAIN / SEQUENCE MATCHES & BONUS ---
        kill_chain_bonus = 0
        if idx in bf_chain:
            triggered_rules.append("KILL_CHAIN_MATCH: BRUTE_FORCE_EXPLOIT (Failed logins -> Success -> High Sensitivity)")
            kill_chain_bonus = 100
            rule_base_score = max(rule_base_score, 95)
        elif idx in de_chain:
            triggered_rules.append("KILL_CHAIN_MATCH: DRIFT_EXFILTRATION (System Drift -> High Sensitivity -> Data Export)")
            kill_chain_bonus = 100
            rule_base_score = max(rule_base_score, 95)
        elif idx in oe_chain:
            triggered_rules.append("KILL_CHAIN_MATCH: OFFHOURS_EXFILTRATION (Night access -> High Sensitivity -> Data Export)")
            kill_chain_bonus = 100
            rule_base_score = max(rule_base_score, 95)

        # --- 5. WEIGHTED RISK SCORING FORMULA ---
        risk_score = (
            rule_base_score * 0.40 +
            drift_score * 0.25 +
            peer_deviation * 0.15 +
            sensitivity_volume * 0.15 +
            kill_chain_bonus * 0.05
        )
        
        # Add modifier if login request failed
        if status == 'failure':
            risk_score += 5
            
        risk_score = min(float(risk_score), 100.0)
        
        # Classify Severity Tiers
        severity = "LOW"
        if risk_score >= 82:
            severity = "CRITICAL"
        elif risk_score >= 67:
            severity = "HIGH"
        elif risk_score >= 38:
            severity = "MEDIUM"
            
        # Create final result output dictionary
        event_result = {
            'index': idx,
            'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': user_id,
            'username': username,
            'action': action,
            'resource': resource,
            'resource_sensitivity': sensitivity,
            'status': status,
            'source_ip': source_ip_cleanup(row['source_ip']),
            'time_classification': time_class,
            'department': department,
            'job_title': row['job_title'],
            'privilege_level': row['privilege_level'],
            'systems_access': systems_access,
            
            # New indicators
            'drift_score': float(drift_score),
            'peer_deviation': float(peer_deviation),
            'sensitivity_volume': float(sensitivity_volume),
            'kill_chain_match': (kill_chain_bonus > 0),
            'rule_base_score': float(rule_base_score),
            'kill_chain_bonus': float(kill_chain_bonus),
            'confidence_score': min(100, int((len(triggered_rules) * 15) + (drift_score * 0.4) + (peer_deviation * 0.3))),
            
            'risk_score': risk_score,
            'severity': severity,
            'triggered_rules': triggered_rules,
            'drift_signals': drift_signals,
            'system_drift': system_drift,
            'hours_drift': hours_drift,
            'is_stale': is_stale
        }
        
        results.append(event_result)
        
    return pd.DataFrame(results)

def source_ip_cleanup(ip):
    if pd.isna(ip):
        return "unknown"
    return str(ip)

# --- [6] AI INVESTIGATION & BLAST RADIUS LAYER ---

def analyze_blast_radius(user_profile, action=None, sensitivity=None):
    """
    Calculates quantitative blast radius metrics.
    Adds count of critical systems accessible and estimated records exposure.
    """
    systems_str = user_profile.get('systems_access', '')
    privilege = user_profile.get('privilege_level', 'user')
    
    if not systems_str:
        systems = []
    else:
        systems = [s.strip().upper() for s in systems_str.split('|')]
        
    # 1. Count of critical systems accessible
    critical_targets = ['PROD_DB', 'ADMIN_SYS', 'SIEM', 'GCP', 'AWS_IAM', 'AZURE_AD']
    critical_accessible_count = sum(1 for sys in systems if sys in critical_targets)
    if privilege == 'admin' and critical_accessible_count == 0:
        critical_accessible_count = 1 # admin always has at least one control path
        
    # 2. Estimated record exposure numbers based on action and sensitivity
    estimated_records = 0
    if action == 'export_data':
        if sensitivity == 'high':
            estimated_records = 50000
        elif sensitivity == 'medium':
            estimated_records = 10000
        else:
            estimated_records = 5000
    elif action in ['sql_query', 'file_access', 'api_call']:
        if sensitivity == 'high':
            estimated_records = 2000
        elif sensitivity == 'medium':
            estimated_records = 500
        else:
            estimated_records = 100
            
    # Category level definition
    level = 'LOW'
    impact_desc = 'Minimal direct database or cloud infrastructure access privileges.'
    
    if privilege == 'admin' or any(sys in ['PROD_DB', 'ADMIN_SYS', 'SIEM'] for sys in systems):
        level = 'CRITICAL'
        impact_desc = 'Administrative access to core databases, domain controller systems, or log audits. High risk of complete database exfiltration.'
    elif any(sys in ['GCP', 'AWS_IAM', 'AZURE_AD'] for sys in systems):
        level = 'HIGH'
        impact_desc = 'Cloud control plane or identity management system credentials. Exposure could allow horizontal movement across infrastructure services.'
    elif any(sys in ['EMAIL', 'VPN', 'AD', 'SALESFORCE', 'SERVICENOW'] for sys in systems):
        level = 'MEDIUM'
        impact_desc = 'Access to business operations, communication files, or SaaS data (Customer PII/HR records).'
        
    return {
        'level': level,
        'impact_description': impact_desc,
        'critical_systems_count': critical_accessible_count,
        'estimated_records_exposed': estimated_records
    }

def generate_ai_narrative(alert_data, user_profile, live_ai=False):
    """
    Generates SOC analyst narratives explaining the threat context.
    """
    username = alert_data['username']
    action = alert_data['action']
    resource = alert_data['resource']
    time_class = alert_data['time_classification']
    score = alert_data['risk_score']
    severity = alert_data['severity']
    
    dept = alert_data['department']
    job_title = alert_data['job_title']
    priv_level = alert_data['privilege_level']
    
    triggered_rules = alert_data['triggered_rules']
    
    # Fetch blast radius stats
    blast = analyze_blast_radius(user_profile, action, alert_data['resource_sensitivity'])
    
    narrative_parts = []
    
    # 1. Headline summary
    narrative_parts.append(
        f"The system raised a {severity} alert (Risk Score: {score:.0f}/100) for user {username} "
        f"({job_title} in the {dept} department, operating with '{priv_level}' privileges)."
    )
    
    # 2. Action Description
    narrative_parts.append(
        f"The alert was triggered when the account performed a '{action}' action on '{resource}' "
        f"during {time_class} hours."
    )
    
    # 3. Threat details (drift indicators)
    analysis_reasons = []
    if alert_data['is_stale']:
        analysis_reasons.append("the credentials belong to a stale or inactive user profile, indicating high risk of compromised session reuse")
    if alert_data['system_drift']:
        analysis_reasons.append(f"the resource '{resource}' represents a System Drift, as it has never been accessed historically by this account")
    if alert_data['hours_drift']:
        analysis_reasons.append(f"the access timing is a Time Drift, which is highly abnormal compared to the historical occupancy profile of this user")
    
    # Check specific rule matches
    rule_reasons = []
    for rule in triggered_rules:
        if "PRIVILEGE" in rule:
            rule_reasons.append("violating privilege policies by executing admin tasks from a standard user role")
        if "HIGH_SENSITIVITY" in rule:
            rule_reasons.append("querying restricted or highly sensitive tables outside normal business hours")
        if "FAILED_LOGIN" in rule:
            rule_reasons.append("showing patterns of a credential brute force attack (sequential login failures immediately prior to success)")
        if "UNAUTHORIZED" in rule:
            rule_reasons.append("attempting to access an endpoint that is not approved in their profile credentials")
        if "KILL_CHAIN_MATCH" in rule:
            rule_reasons.append(f"matching advanced sequence progression indicators ({rule.split(':')[1].strip()})")
            
    all_reasons = analysis_reasons + rule_reasons
    if all_reasons:
        reasons_joined = "; ".join(all_reasons)
        narrative_parts.append(f"Suspicious indicators identified: {reasons_joined[0].upper() + reasons_joined[1:]}.")
    else:
        narrative_parts.append("This alert was raised due to generalized statistical baseline variance in query rates.")
        
    # 4. Blast Radius statement with quantitative elements
    narrative_parts.append(
        f"Impact Assessment: The user holds credentials allowing access to '{user_profile.get('systems_access', 'none')}' systems. "
        f"The potential Blast Radius is evaluated as {blast['level']} because the user has administrative access to "
        f"{blast['critical_systems_count']} critical business systems. The estimated records exposure from this specific action "
        f"is approximately {blast['estimated_records_exposed']:,} records. Description: {blast['impact_description']}"
    )
    
    # 5. Recommendation actions
    rec_actions = []
    if severity == "CRITICAL":
        rec_actions = [
            "Immediately terminate active user sessions and disable the LDAP/AD account.",
            "Verify with department management if this action corresponds to emergency or out-of-band maintenance operations.",
            "Inspect the last 72 hours of audit logs for this source IP to look for horizontal network movements."
        ]
    elif severity == "HIGH":
        rec_actions = [
            "Enable temporary session monitoring for the account.",
            "Contact the employee to verify the legitimacy of this off-hours session.",
            "Validate resource access logs to ensure no bulk data export was successfully completed."
        ]
    else:
        rec_actions = [
            "Flag the account for review in the weekly access audit.",
            "Monitor baseline drift rates for the next 7 days."
        ]
        
    narrative_parts.append("Recommended Mitigation Steps:")
    for idx, act in enumerate(rec_actions, 1):
        narrative_parts.append(f" {idx}. {act}")
        
    return "\n\n".join(narrative_parts)

def build_complete_pipeline():
    """
    Main orchestrator that runs the data loading, enrichment, baselining, scoring, 
    and returns a combined results package.
    """
    logs, profiles = load_data()
    enriched = enrich_data(logs, profiles)
    user_baselines, dept_baselines, peer_baselines = build_behavioral_profiles(enriched)
    results_df = detect_threats_and_score(enriched, dept_baselines, peer_baselines)
    
    # Map index to user profile for quick lookup in narrative calls
    profiles_dict = profiles.set_index('user_id').to_dict('index')
    
    # Add AI narrative summaries to scored alerts
    narratives = []
    blast_details = []
    for _, row in results_df.iterrows():
        user_id = row['user_id']
        u_prof = profiles_dict.get(user_id, {
            'systems_access': '', 'privilege_level': 'user', 'department': 'unknown'
        })
        
        # Calculate blast radius specs
        blast = analyze_blast_radius(u_prof, row['action'], row['resource_sensitivity'])
        blast_details.append(blast)

        # Generate narrative (Gemini Explainer with Fallback)
        try:
            if row['severity'] == 'CRITICAL':
                from src.llm_explainer import explain_alert_with_gemini
                alert_dict = row.to_dict()
                alert_dict['estimated_records_exposed'] = blast['estimated_records_exposed']
                narrative = explain_alert_with_gemini(alert_dict)
            else:
                narrative = generate_ai_narrative(row, u_prof)
        except Exception as e:
            # Fallback narrative
            narrative = generate_ai_narrative(row, u_prof)
            
        narratives.append(narrative)
        
    results_df['ai_narrative'] = narratives
    results_df['blast_level'] = [b['level'] for b in blast_details]
    results_df['blast_desc'] = [b['impact_description'] for b in blast_details]
    results_df['critical_systems_count'] = [b['critical_systems_count'] for b in blast_details]
    results_df['estimated_records_exposed'] = [b['estimated_records_exposed'] for b in blast_details]
    
    return results_df, profiles, user_baselines
