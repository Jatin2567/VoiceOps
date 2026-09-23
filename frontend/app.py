"""VoiceOps Enterprise: Streamlit Observability & Benchmarking Dashboard."""
import os

import httpx
import streamlit as st

from frontend.components.audit_ledger import render_audit_ledger
from frontend.components.metrics_display import render_metrics_display
from frontend.components.session_controls import render_session_controls
from frontend.components.waterfall_chart import render_waterfall_chart

# Page Configuration
st.set_page_config(
    page_title="VoiceOps Enterprise | Observability & TTFA Benchmarking",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-Aesthetic Styling
st.markdown("""
<style>
    /* Dark Mode Glassmorphism & High-End Card Styling */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }
    .header-badge {
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
        color: #0f172a;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Resolve Backend API URL from environment
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# Sidebar Configuration & Architecture Guide
with st.sidebar:
    st.image(
        "https://raw.githubusercontent.com/pipecat-ai/pipecat/main/docs/static/img/pipecat-logo.png",
        width=180,
    )
    st.markdown("### ⚡ System Status")

    # Backend Health Check
    backend_online = False
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{BACKEND_API_URL}/health")
            if resp.status_code == 200:
                backend_online = True
    except Exception:
        backend_online = False

    if backend_online:
        st.success(f"🟢 Backend Online (`{BACKEND_API_URL}`)")
    else:
        st.error(f"🔴 Backend Offline (`{BACKEND_API_URL}`)")
        st.caption("Ensure FastAPI is running: `uvicorn backend.main:app --port 8000`")

    st.markdown("---")
    st.markdown("#### 📐 Architecture Directives")
    st.markdown("""
    - **Directive 1:** Unified Pipecat DAG (`AudioRawFrame`, `TextFrame`, `EndFrame`)
    - **Directive 2:** Non-blocking ASGI (`asyncio.create_task`)
    - **Directive 3:** Custom Subprocess Edge-TTS (`TTSService`)
    - **Directive 4:** Non-invasive TTFA ($T_0 \to T_1$) Outbox Pattern
    - **Directive 5:** Deterministic Sidecar Interceptor
    """)

    st.markdown("---")
    st.caption("VoiceOps Enterprise v0.1.0 • Built with Hexagonal Architecture")

# Main Header
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown('<div class="header-badge">ZERO-COST TELEMETRY PLATFORM</div>', unsafe_allow_html=True)
    st.title("🎙️ VoiceOps Enterprise")
    st.markdown(
        "**Quantitative Time-to-First-Audio (TTFA) Latency Benchmarking & Deterministic Policy Guardrails**"
    )

with header_col2:
    st.metric(
        label="Outbox Architecture",
        value="Redis ➔ Supabase",
        delta="Zero Audio Drag",
    )

st.markdown("---")

# Section 1: Session Controls & Trigger
active_trace_id = render_session_controls(backend_url=BACKEND_API_URL)

st.markdown("---")

# Section 2: Real-time Telemetry Polling & TTFA KPI Display
result_data = render_metrics_display(backend_url=BACKEND_API_URL, trace_id=active_trace_id)

# Section 3: Latency Distribution Waterfall & Audit Ledger
if result_data:
    st.markdown("---")
    chart_col, ledger_col = st.columns([1, 1])

    with chart_col:
        render_waterfall_chart(result_data)

    with ledger_col:
        render_audit_ledger(backend_url=BACKEND_API_URL, active_result=result_data)
else:
    # Render historical ledger when idle
    render_audit_ledger(backend_url=BACKEND_API_URL, active_result=None)
