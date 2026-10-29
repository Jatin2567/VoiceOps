"""Shared in-app operational reference for the deployed demo."""
import streamlit as st
import json
from pathlib import Path


def render_reference():
    st.markdown('<div class="eyebrow">OPERATING GUIDE</div>', unsafe_allow_html=True)
    st.title("Understand every turn.")
    st.write("A practical reference for the voice pipeline, policy checks, debugging, and evaluation.")
    tabs = st.tabs(["How it works", "Debugging", "Reliability", "Evaluation"])
    with tabs[0]:
        st.subheader("One voice stack. Two ways to explore.")
        st.write("Live call: browser microphone → 16 kHz WAV → Groq Whisper → Groq reasoning → deterministic booking tools → Edge-TTS → browser playback. Each turn runs through Pipecat.")
        st.write("Benchmark lab compares Cascade and Hybrid. Microphone calls always use Hybrid. A call retains conversation context and tool results between recordings.")
        st.info("This is a turn-based demo clinic, not full-duplex telephony. Bookings are real mutations in an isolated in-memory demo store, not a production scheduling system.")
        st.caption("Groq receives recorded speech and context. Edge-TTS receives reply text. Calls are not added to the public benchmark history.")
    with tabs[1]:
        st.subheader("Find the failure, not a guess.")
        st.table([
            {"Symptom": "Microphone unavailable", "Check": "Use HTTPS; allow microphone access; check OS input device permissions."},
            {"Symptom": "No audible reply", "Check": "Press Play; browser autoplay may be blocked. Check system volume."},
            {"Symptom": "Call expired", "Check": "Start a new call. Free instances restart and sleep; sessions are temporary."},
            {"Symptom": "Provider error / timeout", "Check": "Copy the trace ID; inspect Render logs; verify GROQ_API_KEY and GROQ_LLM_MODEL."},
            {"Symptom": "Booking conflict", "Check": "Review Booking activity. Use another UTC slot or cancel the previous appointment."},
            {"Symptom": "Connection interrupted", "Check": "Resend the same recording. Its turn ID prevents duplicate execution within this session."},
        ])
        st.code("pytest -q\npython scripts/evaluate_voice.py --base-url http://127.0.0.1:8000", language="bash")
        st.caption("Keep keys, full transcripts, and phone numbers out of public bug reports. Report trace ID, stage, mode, timestamp, and sanitized error details.")
    with tabs[2]:
        st.subheader("Explicit limits. Predictable recovery.")
        st.write("30-second input limit; 60-second pipeline deadline; two concurrent voice turns; one active turn per call; 24 call rooms; 12 turns per call; 30-minute idle expiry. A failed process stops the combined Render service so health checks can detect it.")
        st.write("Tool calls are serialized per call. Repeated turn IDs retrieve cached outcomes. If synthesis fails after a booking action, inspect Booking activity before repeating the request. Sessions and idempotency records do not survive restarts.")
        st.warning("Free hosting sleeps when idle. Bookings are ephemeral and unauthenticated demo data. Do not use real patient information or treat this as production scheduling.")
        st.caption("TTFA is measured from the backend speech-end marker to first generated audio. Browser upload and playback delay are additional; this is not end-user mouth-to-ear latency.")
    with tabs[3]:
        st.subheader("Test behavior, not just fluent replies.")
        report_path = Path(__file__).parents[1] / "assets" / "evaluation.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            st.caption(f"Recorded local provider evaluation · {report['timestamp_utc']} · not a continuous uptime check")
            st.dataframe(report["cases"], hide_index=True, width="stretch")
        st.write("The live evaluation generates synthetic spoken requests, sends them through real Groq and Edge-TTS, and verifies booking state plus tool checks. It never uses real customer data.")
        st.table([
            {"Case": "New appointment", "Expected": "One confirmed booking; a tool check; playable audio."},
            {"Case": "Occupied slot", "Expected": "No second booking in the same slot."},
            {"Case": "Cancel previous booking", "Expected": "The correct booking becomes cancelled using retained context."},
            {"Case": "Unknown booking ID", "Expected": "No mutation; policy error or clarification."},
            {"Case": "Cancellation within two hours", "Expected": "Blocked; booking stays confirmed."},
            {"Case": "Duplicate turn", "Expected": "Same trace and booking result, no repeated action."},
        ])
        st.caption("A model may ask for clarification instead of calling a tool. Evaluation reports distinguish that from a verified policy block. Passing a few cases does not establish a reliability percentage.")
    st.link_button("Source code & evaluation guide", "https://github.com/Jatin2567/VoiceOps/tree/codex/render-deploy")
