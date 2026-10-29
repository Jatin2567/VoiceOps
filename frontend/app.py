"""VoiceOps: a focused workspace for voice AI benchmarking."""
import os
from pathlib import Path

import httpx
import streamlit as st

from frontend.components.live_call import render_live_call
from frontend.components.reference import render_reference
from frontend.components.audit_ledger import render_audit_ledger
from frontend.components.metrics_display import render_metrics_display
from frontend.components.session_controls import render_session_controls
from frontend.components.waterfall_chart import render_waterfall_chart

st.set_page_config(page_title="VoiceOps — Conversations into actions", page_icon="◉",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"<style>{Path(__file__).with_name('assets').joinpath('theme.css').read_text()}</style>",
            unsafe_allow_html=True)
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

try:
    with httpx.Client(timeout=2.0) as client:
        backend_online = client.get(f"{BACKEND_API_URL}/health").status_code == 200
except httpx.HTTPError:
    backend_online = False

status = "SYSTEM ONLINE" if backend_online else "SYSTEM UNAVAILABLE"
st.markdown(f'<header class="masthead"><div class="wordmark"><span>▥</span> voiceops<span class="wordmark-dot">●</span></div><div class="masthead-note">CONVERSATION, WITH CONSEQUENCE.</div><div class="system-state {"online" if backend_online else "offline"}"><i></i>{status}</div></header>', unsafe_allow_html=True)
with st.container(key="workspace_nav"):
    page = st.radio("Workspace", ["Live call", "Benchmark lab", "Run history", "Reference"],
                    horizontal=True, label_visibility="collapsed", key="workspace_page")
if not backend_online:
    st.warning("The voice service is unavailable. Free hosting may need a moment to wake up; refresh shortly.")
if page == "Live call":
    render_live_call(BACKEND_API_URL, backend_online)
elif page == "Benchmark lab":
    st.markdown('''<section class="page-intro"><div class="eyebrow">THE BENCHMARK LAB / 02</div>
    <h1>Measure what<br><em>makes it work.</em></h1>
    <p>Compare voice pipelines. Follow the latency. See exactly where policies intervene.</p></section>''',
                unsafe_allow_html=True)
    with st.container(border=True):
        active_trace_id = render_session_controls(backend_url=BACKEND_API_URL)
    st.markdown("### The conversation, measured.")
    st.caption("Response speed, pipeline performance, and policy decisions in one place.")
    result_data = render_metrics_display(BACKEND_API_URL, active_trace_id)
    if result_data and result_data.get("status") == "completed":
        with st.container(border=True):
            render_waterfall_chart(result_data)
    with st.container(border=True):
        render_audit_ledger(BACKEND_API_URL, result_data)
elif page == "Run history":
    st.markdown('<section class="page-intro"><div class="eyebrow">THE RUN ARCHIVE / 03</div><h1>Nothing lost<br><em>in translation.</em></h1></section>', unsafe_allow_html=True)
    st.caption("Review recent benchmarks and the policies that shaped each response.")
    render_audit_ledger(BACKEND_API_URL, None)
else:
    render_reference()
st.markdown('<footer class="site-footer"><span class="footer-brand">voiceops.</span><span>Built for listening. Designed for clarity.</span><span>DEMO WORKSPACE · 2026</span></footer>', unsafe_allow_html=True)
