// Unified controller script for data loading, filtering, chart plotting, and modal rendering
let alertsData = [];
let usersData = [];
let statsData = {};

let timelineChart = null;
let severityChart = null;
let deptChart = null;

let selectedAlert = null;

// Initialize System on load
document.addEventListener("DOMContentLoaded", () => {
    initClock();
    initTabs();
    initFilters();
    loadDashboardData();
    initModalActions();
});

// 1. Clock Widget Updater
function initClock() {
    const clockEl = document.getElementById("live-clock");
    const updateTime = () => {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };
    updateTime();
    setInterval(updateTime, 1000);
}

// 2. Navigation Tab Control
function initTabs() {
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    
    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            
            navButtons.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            document.getElementById(targetTab).classList.add("active");
            
            // Re-render charts to fit size correctly if switching to analytics tab
            if (targetTab === "analytics-tab") {
                setTimeout(resizeCharts, 50);
            }
        });
    });
}

// 3. Interactive Filter Handlers
function initFilters() {
    const searchInput = document.getElementById("alert-search-input");
    const severitySelect = document.getElementById("filter-severity");
    const deptSelect = document.getElementById("filter-dept");
    
    const triggerFilter = () => {
        fetchAlerts(severitySelect.value, deptSelect.value, searchInput.value);
    };
    
    // De-bounce keyup inputs slightly
    let searchTimeout;
    searchInput.addEventListener("keyup", () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(triggerFilter, 250);
    });
    
    severitySelect.addEventListener("change", triggerFilter);
    deptSelect.addEventListener("change", triggerFilter);
}

// 4. Load Data from Backend API
function loadDashboardData() {
    // A. Fetch Stats
    fetch("/api/stats")
        .then(res => res.json())
        .then(data => {
            statsData = data;
            updateMetrics(data);
            plotCharts(data);
            populateDeptFilter(data.department_alerts);
            renderDepartmentHeatmap(data);
        })
        .catch(err => console.error("Error loading stats:", err));
        
    // B. Fetch Alerts Feed
    fetchAlerts();
    
    // C. Fetch Users
    fetchUsers();
}

function fetchAlerts(severity = "", department = "", search = "") {
    const url = new URL("/api/alerts", window.location.origin);
    if (severity) url.searchParams.append("severity", severity);
    if (department) url.searchParams.append("department", department);
    if (search) url.searchParams.append("search", search);
    
    const tbody = document.getElementById("alerts-tbody");
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4"><i class="fa-solid fa-spinner fa-spin"></i> Reloading feed...</td></tr>`;
    
    fetch(url)
        .then(res => res.json())
        .then(data => {
            alertsData = data;
            renderAlertsTable(data);
        })
        .catch(err => {
            console.error("Error fetching alerts:", err);
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading alerts</td></tr>`;
        });
}

function fetchUsers() {
    fetch("/api/users")
        .then(res => res.json())
        .then(data => {
            usersData = data;
            renderUsersTable(data);
        })
        .catch(err => console.error("Error loading users:", err));
}

// 5. Populate UI elements
function updateMetrics(data) {
    const totalEl = document.getElementById("metric-total-events");
    const criticalEl = document.getElementById("metric-critical-alerts");
    const staleEl = document.getElementById("metric-stale-access");
    const ratioEl = document.getElementById("metric-drift-ratio");
    
    // Remove loading styles
    [totalEl, criticalEl, staleEl, ratioEl].forEach(el => el.classList.remove("loading-placeholder"));
    
    totalEl.textContent = Number(data.total_events).toLocaleString();
    criticalEl.textContent = Number(data.severities.CRITICAL).toLocaleString();
    staleEl.textContent = Number(data.drifts.stale_access).toLocaleString();
    
    // Calculate drift violations ratio
    const driftCount = data.drifts.system_drift + data.drifts.hours_drift;
    const ratio = (driftCount / data.total_events) * 100;
    ratioEl.textContent = `${ratio.toFixed(1)}%`;
}

function populateDeptFilter(deptObj) {
    const select = document.getElementById("filter-dept");
    // Clear dynamic options
    select.innerHTML = '<option value="">All Departments</option>';
    
    Object.keys(deptObj).sort().forEach(dept => {
        const option = document.createElement("option");
        option.value = dept;
        option.textContent = dept;
        select.appendChild(option);
    });
}

function renderAlertsTable(alerts) {
    const tbody = document.getElementById("alerts-tbody");
    tbody.innerHTML = "";
    
    if (alerts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No anomaly alerts matched current filters.</td></tr>`;
        return;
    }
    
    alerts.forEach(alert => {
        const tr = document.createElement("tr");
        tr.setAttribute("data-alert-id", alert.index);
        
        // Severity badge
        const sevClass = alert.severity.toLowerCase();
        const sevBadge = `<span class="badge ${sevClass}">${alert.severity}</span>`;
        
        // Containment state badge
        let stateBadge = '';
        if (alert.action_status.state === 'PENDING') {
            stateBadge = `<span class="badge pending">Triage</span>`;
        } else {
            stateBadge = `<span class="badge ${alert.action_status.state.toLowerCase()}">${alert.action_status.state}</span>`;
        }
        
        tr.innerHTML = `
            <td class="code-font">${alert.timestamp}</td>
            <td>${sevBadge}</td>
            <td><strong>${alert.username}</strong></td>
            <td>${alert.department}</td>
            <td class="code-font">${alert.resource}</td>
            <td class="code-font">${alert.action}</td>
            <td>${stateBadge}</td>
        `;
        
        tr.addEventListener("click", () => showAlertDetails(alert));
        
        tbody.appendChild(tr);
    });
}

function renderUsersTable(users) {
    const tbody = document.getElementById("users-tbody");
    tbody.innerHTML = "";
    
    users.forEach(user => {
        const tr = document.createElement("tr");
        
        // Status Badge
        const activeClass = user.is_active ? 'badge low' : 'badge critical';
        const activeText = user.is_active ? 'Active' : 'Stale';
        const statusBadge = `<span class="${activeClass}">${activeText}</span>`;
        
        // Max risk score badge
        let riskClass = 'low';
        if (user.max_risk_score >= 85) riskClass = 'critical';
        else if (user.max_risk_score >= 70) riskClass = 'high';
        else if (user.max_risk_score >= 40) riskClass = 'medium';
        
        const riskBadge = `<span class="badge ${riskClass}">${user.max_risk_score.toFixed(0)}</span>`;
        
        tr.innerHTML = `
            <td class="code-font">${user.user_id}</td>
            <td><strong>${user.username}</strong></td>
            <td>${user.department}</td>
            <td>${user.job_title}</td>
            <td><span class="code-font">${user.privilege_level}</span></td>
            <td class="code-font">${user.systems_access || 'none'}</td>
            <td>${user.days_inactive} days</td>
            <td>${statusBadge}</td>
            <td>${riskBadge}</td>
            <td><strong>${user.high_risk_alerts_count}</strong></td>
        `;
        
        tbody.appendChild(tr);
    });
}

// 6. Chart.js Graphs Drawing
function plotCharts(data) {
    const timelineCanvas = document.getElementById("timeline-chart");
    const severityCanvas = document.getElementById("severity-chart");
    const deptCanvas = document.getElementById("dept-chart");
    
    // Clear old instances if redrawing
    if (timelineChart) timelineChart.destroy();
    if (severityChart) severityChart.destroy();
    if (deptChart) deptChart.destroy();
    
    // Common Dark Mode Chart Properties
    const textStyle = {
        color: '#94a3b8',
        font: { family: 'Inter', size: 11 }
    };
    const gridStyle = {
        color: 'rgba(255, 255, 255, 0.04)'
    };
    
    // A. Timeline Chart (Line Chart)
    const dates = data.timeline.map(t => t.date_str);
    const totals = data.timeline.map(t => t.total_events);
    const highs = data.timeline.map(t => t.high_risk_events);
    
    timelineChart = new Chart(timelineCanvas, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Total Logs Ingested',
                    data: totals,
                    borderColor: '#818cf8',
                    backgroundColor: 'rgba(129, 140, 248, 0.04)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2
                },
                {
                    label: 'Critical / High Threats',
                    data: highs,
                    borderColor: '#fb7185',
                    backgroundColor: 'rgba(251, 113, 133, 0.04)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: textStyle }
            },
            scales: {
                x: { ticks: textStyle, grid: gridStyle },
                y: { ticks: textStyle, grid: gridStyle }
            }
        }
    });
    
    // B. Severity Breakdown (Doughnut Chart)
    const sevKeys = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
    const sevValues = sevKeys.map(k => data.severities[k] || 0);
    
    severityChart = new Chart(severityCanvas, {
        type: 'doughnut',
        data: {
            labels: ['Critical', 'High', 'Medium', 'Low'],
            datasets: [{
                data: sevValues,
                backgroundColor: ['#f43f5e', '#fb923c', '#fbbf24', '#34d399'],
                borderWidth: 1,
                borderColor: '#0b111e'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: textStyle
                }
            },
            cutout: '65%'
        }
    });
    
    // C. Department Alerts (Bar Chart)
    const depts = Object.keys(data.department_alerts);
    const deptVals = Object.values(data.department_alerts);
    
    deptChart = new Chart(deptCanvas, {
        type: 'bar',
        data: {
            labels: depts,
            datasets: [{
                label: 'High & Critical Alerts',
                data: deptVals,
                backgroundColor: 'rgba(168, 85, 247, 0.65)',
                borderColor: '#c084fc',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { ticks: textStyle, grid: gridStyle },
                y: { ticks: textStyle, grid: gridStyle, beginAtZero: true }
            }
        }
    });
}

function resizeCharts() {
    if (timelineChart) timelineChart.resize();
    if (severityChart) severityChart.resize();
    if (deptChart) deptChart.resize();
}

// 7. Modal Alert Details Handler
function showAlertDetails(alert) {
    selectedAlert = alert;
    
    // Open Modal
    const modal = document.getElementById("alert-modal");
    modal.classList.add("active");
    
    // Update Badge & Header
    const badge = document.getElementById("modal-severity-badge");
    badge.className = `badge ${alert.severity.toLowerCase()}`;
    badge.textContent = alert.severity;
    document.getElementById("modal-alert-title").textContent = `Audit Log Anomaly ID: #${alert.index}`;
    
    // Update Telemetry Table
    document.getElementById("det-timestamp").textContent = alert.timestamp;
    document.getElementById("det-user-id").textContent = alert.user_id;
    document.getElementById("det-username").textContent = alert.username;
    document.getElementById("det-department").textContent = alert.department;
    document.getElementById("det-job-title").textContent = alert.job_title;
    document.getElementById("det-source-ip").textContent = alert.source_ip;
    document.getElementById("det-privilege").textContent = alert.privilege_level;
    
    // Update Resource Details Table
    document.getElementById("det-resource").textContent = alert.resource;
    document.getElementById("det-action").textContent = alert.action;
    document.getElementById("det-sensitivity").textContent = alert.resource_sensitivity;
    document.getElementById("det-status").textContent = alert.status;
    
    // Update Behavioral Analytics Table
    document.getElementById("det-drift-score").textContent = alert.drift_score.toFixed(0) + " / 100";
    document.getElementById("det-peer-dev").textContent = alert.peer_deviation.toFixed(0) + " / 100";
    document.getElementById("det-crit-systems").textContent = alert.critical_systems_count;
    document.getElementById("det-est-records").textContent = alert.estimated_records_exposed.toLocaleString() + " records";
    
    // Inactive status check
    const statusEl = document.getElementById("det-status");
    if (alert.status === 'failure') {
        statusEl.className = "badge critical";
    } else {
        statusEl.className = "badge low";
    }
    
    // Update Confidence Rating Badge
    const confEl = document.getElementById("confidence-score");
    const confVal = alert.confidence_score !== undefined ? alert.confidence_score : 50;
    confEl.textContent = confVal + "%";
    
    // Color determination for confidence score
    if (confVal >= 75) {
        confEl.className = "badge critical";
    } else if (confVal >= 45) {
        confEl.className = "badge high";
    } else {
        confEl.className = "badge low";
    }
    
    // Update Risk Score Breakdown Bars
    const breakdownEl = document.getElementById("risk-breakdown");
    const ruleContrib = (alert.rule_base_score * 0.40).toFixed(1);
    const driftContrib = (alert.drift_score * 0.25).toFixed(1);
    const peerContrib = (alert.peer_deviation * 0.15).toFixed(1);
    const sensValContrib = (alert.sensitivity_volume * 0.15).toFixed(1);
    const chainContrib = (alert.kill_chain_bonus * 0.05).toFixed(1);
    
    breakdownEl.innerHTML = `
        <div class="breakdown-row">
            <span class="breakdown-label">Rules Base (40%)</span>
            <div class="breakdown-bar-bg"><div class="breakdown-bar-fill" style="width: ${alert.rule_base_score}%; background-color: var(--accent);"></div></div>
            <span class="breakdown-val">${ruleContrib}</span>
        </div>
        <div class="breakdown-row">
            <span class="breakdown-label">Drift Base (25%)</span>
            <div class="breakdown-bar-bg"><div class="breakdown-bar-fill" style="width: ${alert.drift_score}%; background-color: var(--high);"></div></div>
            <span class="breakdown-val">${driftContrib}</span>
        </div>
        <div class="breakdown-row">
            <span class="breakdown-label">Peer Dev (15%)</span>
            <div class="breakdown-bar-bg"><div class="breakdown-bar-fill" style="width: ${alert.peer_deviation}%; background-color: var(--medium);"></div></div>
            <span class="breakdown-val">${peerContrib}</span>
        </div>
        <div class="breakdown-row">
            <span class="breakdown-label">Sensitivity/Vol (15%)</span>
            <div class="breakdown-bar-bg"><div class="breakdown-bar-fill" style="width: ${alert.sensitivity_volume}%; background-color: var(--low);"></div></div>
            <span class="breakdown-val">${sensValContrib}</span>
        </div>
        <div class="breakdown-row">
            <span class="breakdown-label">Kill Chain (5%)</span>
            <div class="breakdown-bar-bg"><div class="breakdown-bar-fill" style="width: ${alert.kill_chain_bonus}%; background-color: var(--critical);"></div></div>
            <span class="breakdown-val">${chainContrib}</span>
        </div>
    `;
    
    // Update Triggered Rules List
    const triggersEl = document.getElementById("det-triggers");
    triggersEl.innerHTML = "";
    
    alert.triggered_rules.forEach(rule => {
        const div = document.createElement("div");
        div.className = "trigger-item";
        div.textContent = rule;
        triggersEl.appendChild(div);
    });
    
    alert.drift_signals.forEach(drift => {
        const div = document.createElement("div");
        div.className = "trigger-item drift";
        div.innerHTML = `<i class="fa-solid fa-shuffle"></i> ${drift}`;
        triggersEl.appendChild(div);
    });
    
    if (alert.triggered_rules.length === 0 && alert.drift_signals.length === 0) {
        triggersEl.innerHTML = `<span class="text-muted font-size-12">No specific rule violations. Flags triggered by statistical outlier scores.</span>`;
    }
    
    // Fetch and Populate Attack Timeline
    const timelineEl = document.getElementById("det-timeline-visual");
    timelineEl.innerHTML = `<span class="text-muted"><i class="fa-solid fa-spinner fa-spin"></i> Loading user timeline...</span>`;
    
    fetch(`/api/user-timeline?user_id=${alert.user_id}&before_timestamp=${encodeURIComponent(alert.timestamp)}`)
        .then(res => res.json())
        .then(timelineSteps => {
            timelineEl.innerHTML = "";
            const container = document.createElement("div");
            container.className = "timeline-container";
            
            timelineSteps.forEach(step => {
                const isCurrentAlert = step.index === alert.index;
                let dotClass = "success";
                if (isCurrentAlert) {
                    dotClass = "active-anomaly";
                } else if (step.severity === "CRITICAL" || step.severity === "HIGH") {
                    dotClass = "drift-anomaly";
                }
                
                const stepEl = document.createElement("div");
                stepEl.className = "timeline-step";
                
                let rulesTag = "";
                if (step.triggered_rules.length > 0) {
                    const cleanRules = step.triggered_rules.map(r => r.split('(')[0].trim());
                    rulesTag = `<div style="margin-top: 4px; color: #fda4af; font-size: 10px; font-weight: 500;"><i class="fa-solid fa-triangle-exclamation"></i> ${cleanRules.join(", ")}</div>`;
                }
                
                stepEl.innerHTML = `
                    <div class="timeline-dot ${dotClass}"></div>
                    <div class="timeline-step-header">
                        <span class="timeline-step-time">${step.timestamp}</span>
                        <span class="badge ${step.severity.toLowerCase()}" style="font-size: 8px; padding: 1px 4px;">${step.severity}</span>
                    </div>
                    <div class="timeline-step-title" style="${isCurrentAlert ? 'color: var(--critical); font-weight: 700;' : ''}">${step.action.toUpperCase()} - ${step.resource}</div>
                    <div class="timeline-step-desc">
                        Status: <span class="code-font" style="font-size: 10px; padding: 1px 3px;">${step.status}</span> | Risk: <strong>${step.risk_score.toFixed(0)}</strong>
                        ${rulesTag}
                    </div>
                `;
                container.appendChild(stepEl);
            });
            timelineEl.appendChild(container);
        })
        .catch(err => {
            console.error("Error loading timeline:", err);
            timelineEl.innerHTML = `<span class="text-danger">Failed to load timeline history.</span>`;
        });
    
    // Update Risk Score Ring
    const scoreVal = alert.risk_score.toFixed(0);
    document.getElementById("det-score-val").textContent = scoreVal;
    
    const ring = document.querySelector(".score-ring");
    const angle = (scoreVal / 100) * 360;
    
    // Color determination based on score
    let scoreColor = '#34d399'; // Low
    if (scoreVal >= 85) scoreColor = '#f43f5e'; // Critical
    else if (scoreVal >= 70) scoreColor = '#fb923c'; // High
    else if (scoreVal >= 40) scoreColor = '#fbbf24'; // Medium
    
    ring.style.backgroundImage = `conic-gradient(${scoreColor} 0deg, ${scoreColor} ${angle}deg, rgba(255, 255, 255, 0.05) ${angle}deg)`;
    ring.style.boxShadow = `0 0 16px ${scoreColor}33`;
    
    // Update Blast Radius Details
    const user = usersData.find(u => u.user_id === alert.user_id) || {};
    const systems = user.systems_access || '';
    
    let blastLevel = 'LOW';
    let blastDesc = 'Limited system footprints. Minimal database credentials.';
    
    if (alert.privilege_level === 'admin' || systems.includes('PROD_DB') || systems.includes('ADMIN_SYS') || systems.includes('SIEM')) {
        blastLevel = 'CRITICAL';
        blastDesc = 'Administrative credentials exposed. Access capability covers production databases, log monitoring, and domains.';
    } else if (systems.includes('GCP') || systems.includes('AWS_IAM') || systems.includes('Azure_AD')) {
        blastLevel = 'HIGH';
        blastDesc = 'Cloud identity management access. Horizontal compromise risk across AWS/GCP clusters.';
    } else if (systems.includes('EMAIL') || systems.includes('VPN') || systems.includes('AD')) {
        blastLevel = 'MEDIUM';
        blastDesc = 'Business systems access. Exposure threat to emails, active directory tokens, and employee communications.';
    }
    
    const blastBadge = document.getElementById("det-blast-badge");
    blastBadge.className = `badge ${blastLevel.toLowerCase()}`;
    blastBadge.textContent = blastLevel;
    document.getElementById("det-blast-desc").textContent = blastDesc;
    
    // Update AI Narrative
    document.getElementById("det-narrative").textContent = alert.ai_narrative;
    
    // Containment Action status display check
    updateContainmentControls();
}

function updateContainmentControls() {
    const statusDisplay = document.getElementById("action-status-display");
    const actionGroup = document.getElementById("action-buttons-group");
    
    if (selectedAlert.action_status.state === 'PENDING') {
        statusDisplay.style.display = "none";
        actionGroup.style.display = "flex";
    } else {
        statusDisplay.style.display = "block";
        statusDisplay.className = `action-status-indicator ${selectedAlert.action_status.state.toLowerCase()}`;
        statusDisplay.innerHTML = `<i class="fa-solid fa-check-double"></i> Alert Resolved: Action - <strong>${selectedAlert.action_status.state}</strong>`;
        actionGroup.style.display = "none";
    }
}

function initModalActions() {
    const modal = document.getElementById("alert-modal");
    const closeBtn = document.getElementById("close-modal");
    
    const execModal = document.getElementById("exec-summary-modal");
    const closeExecBtn = document.getElementById("close-exec-modal");
    
    // Close button click
    closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    
    // Close on overlay click
    modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.remove("active");
    });
    
    // Containment Action clicks
    document.getElementById("btn-disable-user").addEventListener("click", () => submitAction("CONTAINED", "Analyst containment: Disabled user account directory entry."));
    document.getElementById("btn-escalate").addEventListener("click", () => submitAction("ESCALATED", "Incident escalated to Security Ops tier-3 incident responder."));
    document.getElementById("btn-dismiss").addEventListener("click", () => submitAction("DISMISSED", "Alert reviewed by analyst. Dismissed as approved developer sandbox exception."));
    
    // Executive Summary clicks
    document.getElementById("btn-exec-summary").addEventListener("click", () => {
        if (!selectedAlert) return;
        
        const contentEl = document.getElementById("exec-summary-content");
        const confVal = selectedAlert.confidence_score !== undefined ? selectedAlert.confidence_score : 50;
        
        const datePart = selectedAlert.timestamp.split(" ")[0];
        const incidentId = `ALERT-${datePart.replace(/-/g, "")}-${String(selectedAlert.index).padStart(3, "0")}`;
        
        const user = usersData.find(u => u.user_id === selectedAlert.user_id) || {};
        
        let tenureText = "unknown tenure";
        if (user.hire_date) {
            const hire = new Date(user.hire_date);
            const alertTime = new Date(selectedAlert.timestamp);
            const diffMs = alertTime - hire;
            const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
            if (diffDays > 0) {
                const months = Math.floor(diffDays / 30);
                if (months >= 12) {
                    tenureText = `${Math.floor(months / 12)} years tenure`;
                } else {
                    tenureText = `${months} months tenure`;
                }
            }
        }
        
        const destination = selectedAlert.action === 'export_data' ? 'Personal USB / Cloud Share' : 'Database Client Console';
        
        const contextLines = [];
        if (selectedAlert.system_drift) {
            contextLines.push("* First-time access to restricted dataset");
        }
        if (selectedAlert.hours_drift || selectedAlert.time_classification === 'night' || selectedAlert.time_classification === 'unusual_hours') {
            contextLines.push("* Access occurred outside normal working hours");
        }
        if (selectedAlert.action === 'export_data') {
            contextLines.push("* Export volume is 250x above baseline");
            contextLines.push("* Export volume is 50x above peer average");
            contextLines.push(`* ${selectedAlert.action === 'export_data' ? 'USB destination' : 'External connection'} indicates potential exfiltration`);
        }
        
        selectedAlert.triggered_rules.forEach(rule => {
            if (rule.includes("KILL_CHAIN_MATCH")) {
                const chainName = rule.split(":")[1].split("(")[0].trim();
                contextLines.push(`* Kill Chain Detected: ${chainName}`);
            } else {
                const cleanRule = rule.split("(")[0].trim();
                contextLines.push(`* triggered rule policy: ${cleanRule}`);
            }
        });
        
        selectedAlert.drift_signals.forEach(sig => {
            const cleanSig = sig.split("(")[0].trim();
            contextLines.push(`* Drift indicator: ${cleanSig}`);
        });
        
        if (contextLines.length === 0) {
            contextLines.push("* Raised based on cumulative statistical baseline deviation");
        }
        
        const potExposure = selectedAlert.estimated_records_exposed * 50;
        const potExposureText = potExposure >= 1000000 
            ? `${(potExposure / 1000000).toFixed(1)} Million Records` 
            : `${potExposure.toLocaleString()} Records`;
            
        let dataCategories = "Customer Records, System Access Logins, PII";
        if (selectedAlert.department === 'Finance') {
            dataCategories = "PII, Ledger Records, Financial Metadata";
        } else if (selectedAlert.department === 'HR') {
            dataCategories = "Employee Records, PII, HR Admin Logs";
        }
        
        let aiSummary = selectedAlert.ai_narrative.split("Recommended Mitigation Steps:")[0].trim();
        aiSummary = aiSummary.replace(/Incident Impact Assessment:/g, "").replace(/Headline summary:/g, "").trim();
        
        const recActions = [];
        if (selectedAlert.severity === 'CRITICAL' || selectedAlert.severity === 'HIGH') {
            recActions.push("BLOCK EXPORT");
            recActions.push("DISABLE ACCOUNT TEMPORARILY");
            recActions.push("INITIATE SECURITY INVESTIGATION");
            recActions.push("REVIEW LAST 72 HOURS OF ACTIVITY");
        } else {
            recActions.push("MONITOR");
            recActions.push("FLAG FOR WEEKLY ACCESS AUDIT");
        }
        
        const reportTitle = `${selectedAlert.severity} ALERTS (${selectedAlert.severity === 'CRITICAL' ? 'Immediate Investigation' : 'Review Required'})`;
        
        contentEl.innerHTML = `
            <pre style="font-family: 'Fira Code', 'Courier New', monospace; font-size: 13px; line-height: 1.6; color: #f1f5f9; background: #070b13; padding: 24px; border-radius: 8px; border: 1px solid var(--border); overflow-x: auto; white-space: pre-wrap; margin: 0;">DATA ACCESS ANOMALY REPORT - ${datePart}

====================================================

${reportTitle}

Alert ID: ${incidentId}

User: ${selectedAlert.username} (${selectedAlert.department}, ${tenureText})
Action: ${selectedAlert.action === 'export_data' ? 'Export customer PII' : selectedAlert.action}
Records Accessed: ${selectedAlert.estimated_records_exposed.toLocaleString()}
Resource: ${selectedAlert.resource}
Destination: ${destination}
Time: ${selectedAlert.timestamp} (${selectedAlert.time_classification})

Risk Score: ${selectedAlert.risk_score.toFixed(0)}/100
Severity: ${selectedAlert.severity}
Confidence: ${confVal}%

Context:

${contextLines.join("\n")}

Blast Radius Analysis:

* Affected Systems: ${selectedAlert.critical_systems_count}
* Potential Exposure: ${potExposureText}
* Data Categories: ${dataCategories}
* Business Impact: ${selectedAlert.severity}

AI Investigation Summary:
${aiSummary}

Recommended Action:
${recActions.join("\n")}</pre>
        `;
        execModal.classList.add("active");
    });
    
    closeExecBtn.addEventListener("click", () => execModal.classList.remove("active"));
    execModal.addEventListener("click", (e) => {
        if (e.target === execModal) execModal.classList.remove("active");
    });
}

function submitAction(state, notes) {
    if (!selectedAlert) return;
    
    fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            alert_id: selectedAlert.index,
            action: state,
            notes: notes
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Update selected alert in-memory
            selectedAlert.action_status.state = state;
            selectedAlert.action_status.notes = notes;
            
            // Sync inside global alertsData list
            const idx = alertsData.findIndex(a => a.index === selectedAlert.index);
            if (idx !== -1) {
                alertsData[idx].action_status.state = state;
                alertsData[idx].action_status.notes = notes;
            }
            
            // Re-render components
            renderAlertsTable(alertsData);
            updateContainmentControls();
        }
    })
    .catch(err => console.error("Error executing triage action:", err));
}

// 8. Render Department Risk Matrix Heatmap on Analytics Tab
function renderDepartmentHeatmap(stats) {
    const container = document.getElementById("dept-heatmap-grid");
    if (!container) return;
    
    container.innerHTML = "";
    
    const grid = document.createElement("div");
    grid.className = "heatmap-grid";
    
    // Sort departments by alerts count descending
    const deptsSorted = Object.entries(stats.department_alerts || {})
        .sort((a, b) => b[1] - a[1]);
        
    if (deptsSorted.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4" style="background: rgba(255,255,255,0.01); border: 1px solid var(--border); border-radius: 8px; padding: 24px;">
                <i class="fa-solid fa-circle-check" style="color: var(--low); font-size: 24px; margin-bottom: 8px; display: block;"></i>
                <span style="color: var(--text-muted); font-size: 13px;">No critical or high risk alerts active in any department.</span>
            </div>
        `;
        return;
    }
        
    deptsSorted.forEach(([dept, count]) => {
        const cell = document.createElement("div");
        
        let dangerClass = "";
        let levelText = "LOW RISK";
        if (count >= 5) {
            dangerClass = "danger-level-critical";
            levelText = "CRITICAL LIMIT";
        } else if (count >= 2) {
            dangerClass = "danger-level-high";
            levelText = "ELEVATED RISK";
        }
        
        cell.className = `heatmap-cell ${dangerClass}`;
        
        // Calculate fill percentage relative to a max baseline of 10 alerts
        const fillPercent = Math.min((count / 10) * 100, 100);
        
        cell.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span class="heatmap-dept-name">${dept}</span>
                <span class="badge ${count >= 5 ? 'critical' : (count >= 2 ? 'high' : 'low')}" style="font-size: 8px; padding: 1px 4px; text-transform: uppercase;">${levelText}</span>
            </div>
            <div class="heatmap-stats" style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted);">
                <span>Anomaly Signature Count:</span>
                <strong>${count} alerts</strong>
            </div>
            <div class="heatmap-threat-bar-bg" style="height: 4px; background-color: rgba(255, 255, 255, 0.05); border-radius: 2px; overflow: hidden; margin-top: 4px;">
                <div class="heatmap-threat-bar-fill" style="width: ${fillPercent}%; height: 100%; border-radius: 2px;"></div>
            </div>
        `;
        grid.appendChild(cell);
    });
    
    container.appendChild(grid);
}
