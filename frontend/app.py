"""VoiceOps: a focused workspace for voice AI benchmarking."""
import os
from pathlib import Path

import httpx
import streamlit as st

from frontend.components.audit_ledger import render_audit_ledger
from frontend.components.metrics_display import render_metrics_display
from frontend.components.session_controls import render_session_controls
from frontend.components.waterfall_chart import render_waterfall_chart

st.set_page_config(page_title="VoiceOps | Voice intelligence workspace", page_icon="◉",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<style>{Path(__file__).with_name('assets').joinpath('theme.css').read_text()}</style>",
            unsafe_allow_html=True)
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

try:
    with httpx.Client(timeout=2.0) as client:
        backend_online = client.get(f"{BACKEND_API_URL}/health").status_code == 200
except httpx.HTTPError:
    backend_online = False

with st.sidebar:
    st.markdown('<div class="brand"><span>◉</span> VoiceOps<span class="brand-dot">.</span></div>',
                unsafe_allow_html=True)
    st.caption("VOICE INTELLIGENCE WORKSPACE")
    st.markdown("---")
    page = st.radio("Workspace", ["Overview", "Run history", "Architecture guide"],
                    label_visibility="collapsed")
    st.markdown("---")
    st.markdown("**Your environment**")
    if backend_online:
        st.success("Backend connected")
    else:
        st.warning("Backend disconnected")
        st.caption("Start your backend to run benchmarks and load history.")
    with st.expander("Connection details"):
        st.code(BACKEND_API_URL, language=None)
        st.code("uvicorn backend.main:app --port 8000", language="bash")
    st.markdown("---")
    st.markdown("**Small delays. Big differences.**")
    st.caption("Measure every voice interaction. Understand every decision.")
    st.caption("VoiceOps Enterprise · v0.1")

st.markdown('<div class="eyebrow">WORKSPACE / ' + page.upper() + '</div>',
            unsafe_allow_html=True)
if page == "Overview":
    st.markdown('''<section class="hero"><div class="hero-label">BUILT FOR CONVERSATIONS</div>
    <h1>Better voice AI.<br><span>Starts with listening.</span></h1>
    <p>Your space to compare voice pipelines, explore response times, and put guardrails to the test.</p>
    <div class="color-track"><i></i><i></i><i></i><i></i></div></section>''',
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
    st.title("Every run tells a story.")
    st.caption("Review recent benchmarks and the policies that shaped each response.")
    render_audit_ledger(BACKEND_API_URL, None)
else:
    st.title("Three paths. One clear picture.")
    st.caption("Choose the architecture that fits the conversation you want to build.")
    for title, description in [
        ("01 / Cascade", "Speech to text with Groq Whisper, reasoning with Groq LLM, and speech generation with Edge-TTS. Compare each stage of the conversation."),
        ("02 / Hybrid", "Groq and Edge-TTS with deterministic tool guardrails. Inspect booking conflicts and cancellation rules alongside latency."),
    ]:
        with st.container(border=True):
            st.subheader(title)
            st.write(description)
    st.info("Time to first audio (TTFA) measures the wait before an agent starts speaking. Total turn latency measures the complete turn.")
