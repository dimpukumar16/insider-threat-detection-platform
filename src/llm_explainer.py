import os
import google.generativeai as genai

# Try to load environment variables from a .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Manual fallback parsing of .env files to ensure zero dependency requirements
if not os.getenv("GEMINI_API_KEY"):
    for folder in [".", "..", "../.."]:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), env_path_resolve := os.path.join(folder, ".env"))
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == "GEMINI_API_KEY":
                                os.environ["GEMINI_API_KEY"] = v.strip().strip('"').strip("'")
                                break
            except Exception:
                pass

# Retrieve Gemini API Key from environment variables
API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = False

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        HAS_GEMINI = True
    except Exception as e:
        print(f"Error configuring Gemini Client API: {e}")
        HAS_GEMINI = False

def explain_alert_with_gemini(alert):
    """
    Attempts to call the Gemini model to explain the threat alert.
    Raises ValueError if API key is missing.
    """
    if not HAS_GEMINI or not API_KEY:
        raise ValueError("Gemini API key is not configured in the environment.")

    # Parse out kill chain match
    kill_chains = [r.split(":")[1].split("(")[0].strip() for r in alert.get('triggered_rules', []) if "KILL_CHAIN" in r]
    kill_chain = kill_chains[0] if kill_chains else "None"

    prompt = f"""You are a SOC analyst.

Explain this data access anomaly alert:
User: {alert.get('username')} ({alert.get('department')} / {alert.get('job_title')})
Action: {alert.get('action')} on resource {alert.get('resource')} (Sensitivity: {alert.get('resource_sensitivity')})
Time: {alert.get('timestamp')} ({alert.get('time_classification')})
Risk Score: {alert.get('risk_score', 0.0):.1f}/100
Severity: {alert.get('severity')}
Triggered Rules: {alert.get('triggered_rules', [])}
Drift Score: {alert.get('drift_score', 0.0):.1f}
Peer Deviation: {alert.get('peer_deviation', 0.0):.1f}
Kill Chain: {kill_chain}
Estimated Records Exposed: {alert.get('estimated_records_exposed', 0):,}

Generate:
1. Business Context
2. Investigation Narrative
3. Recommended Actions

Keep the entire response under 150 words. Be concise and professional.
"""
    # Use standard gemini-1.5-flash for rapid, lightweight narrative summaries
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text.strip()
