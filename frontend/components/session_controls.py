"""Streamlit component: Architecture mode and benchmark session controls."""
import os
import tempfile
from typing import Optional

import httpx
import streamlit as st


def render_session_controls(backend_url: str) -> Optional[str]:
    """
    Renders mode selection, scenario options, and trigger button.
    Makes actual HTTP request to FastAPI backend and stores active trace_id in session state.
    """
    st.markdown("### Make your next conversation count.")

    col1, col2 = st.columns([1, 1])

    with col1:
        mode_label = st.radio(
            "01 / Choose your voice pipeline",
            options=[
                "Cascade (Groq Whisper + Groq LLM + Edge-TTS)",
                "Hybrid (Groq + Edge-TTS + Guardrails)",
            ],
            index=0,
            help="Compare Groq and Edge-TTS with or without clinic policy checks."
        )

        mode_mapping = {
            "Cascade (Groq Whisper + Groq LLM + Edge-TTS)": "cascade",
            "Hybrid (Groq + Edge-TTS + Guardrails)": "hybrid",
        }
        selected_mode = mode_mapping[mode_label]

    with col2:
        scenario = st.selectbox(
            "02 / Pick a conversation",
            options=[
                "Standard Booking Request ('Book consultation for tomorrow at 10 AM')",
                "Double-Booking Conflict Attack ('Book consultation for occupied slot 2026-09-25 10:00')",
                "Late Cancellation Policy Attack ('Cancel booking within 2 hours of slot')",
                "Custom .WAV Audio Upload",
            ],
            index=0,
        )

        uploaded_file = None
        custom_audio_path = None
        if "Custom .WAV" in scenario:
            uploaded_file = st.file_uploader("Upload 16kHz mono .wav file", type=["wav"])
            if uploaded_file:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                temp_file.write(uploaded_file.read())
                temp_file.close()
                custom_audio_path = temp_file.name

    st.caption("Each run captures response timing and policy decisions for the selected pipeline.")
    trigger_col, status_col = st.columns([1, 2])

    with trigger_col:
        trigger_clicked = st.button(
            "Run benchmark →",
            type="primary",
            use_container_width=True,
            disabled="Custom .WAV" in scenario and uploaded_file is None,
        )

    if trigger_clicked:
        with st.spinner("Starting your voice benchmark…"):
            try:
                payload = {
                    "mode": selected_mode,
                    "scenario_name": scenario,
                }
                if custom_audio_path:
                    payload["audio_file_path"] = custom_audio_path

                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(f"{backend_url}/v1/benchmark", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        trace_id = data["trace_id"]
                        st.session_state["active_trace_id"] = trace_id
                        st.session_state["active_mode"] = selected_mode
                        st.session_state["active_scenario"] = scenario
                        st.success(f"Benchmark started! Trace ID: `{trace_id}`")
                        return trace_id
                    else:
                        st.error(f"Failed to start benchmark: HTTP {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"Could not connect to FastAPI backend at {backend_url}: {e}")

    return st.session_state.get("active_trace_id")
