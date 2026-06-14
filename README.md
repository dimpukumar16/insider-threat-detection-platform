# Insider Threat Detection Platform

An explainable cybersecurity platform for detecting suspicious data access patterns, insider threats, privilege misuse, and potential data exfiltration attempts.

The platform combines behavioral analytics, peer-group intelligence, risk scoring, blast-radius assessment, and AI-assisted investigation narratives to help security teams prioritize and investigate high-risk activities.

---

## The Challenge

Enterprises generate millions of daily data access events across databases, cloud clusters, and file systems. Legitimate operations hide malicious anomalies, such as compromised credentials, pre-resignation data exfiltrations, and policy violations. 

Traditional security systems rely on naive static rules that produce over **80% false positive rates**, causing severe analyst alert fatigue while real threats go unnoticed for weeks or months.

---

## Features

### Behavioral Profiling

Builds historical user baselines using:

* Access patterns
* Resource usage
* Time affinity
* Activity frequency

### Behavioral Drift Detection

Measures deviations from a user's historical behavior to identify suspicious activities.

### Peer Group Analysis

Compares user behavior against peers with similar departments and job roles.

### Multi-Layer Threat Detection

Detects:

* Stale account activity
* Unauthorized resource access
* Privilege violations
* High-sensitivity off-hours access
* Suspicious activity sequences

### Risk Scoring Engine

Calculates weighted risk scores using:

* Rule severity
* Behavioral drift
* Peer deviation
* Data sensitivity
* Kill-chain evidence

### Blast Radius Analysis

Estimates:

* Systems impacted
* Records exposed
* Business impact

### AI Investigation Narratives

Generates:

* Investigation summaries
* Business context
* Recommended actions
* Executive reports

---

## Architecture

```text
Raw Access Logs + User Profiles
            ↓
Data Ingestion & Enrichment
            ↓
Behavioral Profiling Engine
            ↓
Multi-Layer Detection Engine
            ↓
Risk Scoring Engine
            ↓
Threat Context Engine
            ↓
AI Security Analyst Layer
            ↓
Dashboard & Reporting
```

### 📂 File Map
* **[app.py](app.py)**: Flask backend API serving metrics, alerts database, chronological timeline segments, and persisting triage actions.
* **[src/detector.py](src/detector.py)**: Pipeline engine orchestrator. Manages ingestion, enrichment, behavioral baselines, threat rule signatures, sequence kill chains, risk scoring weights, and blast radius calculation.
* **[src/llm_explainer.py](src/llm_explainer.py)**: Gemini API client integration for automated AI incident summary generation (with robust local template failover).
* **[static/](static/)**: Glassmorphism console assets:
  * **[index.html](static/index.html)**: Structural layout (Feed log, user profile database, analytics, metrics validation tab, detail modal overlays, and report prints).
  * **[app.js](static/app.js)**: Controller script (API data loading, Chart.js integrations, modal toggles, and printing templates).
  * **[style.css](static/style.css)**: Stylesheet (dark-theme theme, grids, heatmap grids, timeline cards, and media print directives).

---

## Dashboard Modules

### Threat Alerts

Prioritized alert management and investigation.

### User Accounts Audit

User profile analysis and access governance.

### Security Analytics

Risk visualization, heatmaps, and trend analysis.

### Executive Reports

Printable incident investigation reports.

---

## Technology Stack

### Backend

* Python
* Flask
* Pandas
* NumPy

### Frontend

* HTML
* CSS
* JavaScript
* Chart.js

### AI

* Google Gemini API
* Template Fallback Engine

---

## Installation

```bash
git clone https://github.com/dimpukumar16/insider-threat-detection-platform.git

cd insider-threat-detection-platform

pip install -r requirements.txt

python app.py
```


