# Insider Threat Detection Platform

An Explainable Insider Threat Detection Platform built for **Societe Generale Hackathon 2026 – PS4: Data Access Audit & Insider Threat Detection**.

## Team

**Team Name:** Infinity One

**Member:** Dimpu Kumar

---

## Problem Statement

Organizations generate thousands of data access events daily, making it difficult for security teams to identify insider threats, unauthorized access, privilege misuse, and data exfiltration attempts.

Our solution provides explainable threat detection using behavioral analytics, peer-group intelligence, risk scoring, and AI-assisted investigation support.

---

## Key Features

* Behavioral Drift Detection
* Peer Group Deviation Analysis
* Multi-Layer Threat Detection
* Kill Chain Detection
* Risk Scoring & Prioritization
* Blast Radius Analysis
* AI Investigation Narratives
* Executive Incident Reports
* Security Analytics Dashboard

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

### AI Layer

* Google Gemini API
* Template Fallback Engine

---

## Dashboard Modules

### Threat Alerts

Investigate prioritized security alerts with risk scores and explanations.

### User Accounts Audit

Review user profiles, privileges, approved systems, and inactivity history.

### Security Analytics

Organization-wide threat visibility through charts and heatmaps.

### Executive Reports

Generate printable incident investigation reports.

---

## Dataset

Available Files:

* user_profiles.csv
* data_access_logs.csv

### Note

The problem statement referenced:

* user_profile_labels.csv
* data_access_labels.csv

However, these ground-truth label files were not included in the dataset package available to participants.

Therefore, supervised evaluation metrics such as Precision, Recall, and F1 Score could not be reproduced locally.

---

## Installation

```bash
git clone https://github.com/dimpukumar16/insider-threat-detection-platform.git
cd insider-threat-detection-platform

pip install -r requirements.txt

python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## Future Enhancements

* Real-Time Streaming Detection
* SIEM Integration
* Automated Response Actions
* Advanced LLM Investigation Assistant
* Cross-System Threat Correlation

---

## Project Deliverables

* Source Code
* Documentation
* Presentation
* Demo Video

---

Developed for **Societe Generale Hackathon 2026**.
