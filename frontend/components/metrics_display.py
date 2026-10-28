"""Streamlit component: Real-time telemetry polling and TTFA metrics display."""
import time
from typing import Any, Dict, Optional

import httpx
import streamlit as st


def render_metrics_display(backend_url: str, trace_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Polls FastAPI /v1/telemetry/{trace_id} until status is completed or failed,
    then renders high-impact KPI cards and conversational balloons.
    """
    if not trace_id:
        st.markdown('<div class="empty-state"><strong>Your first insight starts here.</strong><p>Choose a pipeline and run a benchmark. Your latency, transcript, and policy results will appear here.</p></div>', unsafe_allow_html=True)
        return None

    status_placeholder = st.empty()

    result_data: Optional[Dict[str, Any]] = None
    max_retries = 90
    delay_s = 0.5

    # Real-time polling loop
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{backend_url}/v1/telemetry/{trace_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")

                    if status in ("completed", "failed"):
                        result_data = data
                        break
                    else:
                        status_placeholder.info(
                            f"⏳ Pipeline running in background... Observability probe active (Poll {attempt + 1}/{max_retries})"
                        )
                elif resp.status_code == 404:
                    status_placeholder.warning("Waiting for trace initialization in Outbox queue...")
        except Exception as e:
            status_placeholder.error(f"Polling error: {e}")

        time.sleep(delay_s)

    status_placeholder.empty()

    if not result_data:
        st.error(f"Timed out polling metrics for trace `{trace_id}`.")
        return None

    # Status badge
    exec_status = result_data.get("status", "unknown").upper()
    if exec_status == "COMPLETED":
        st.success(f"✅ Turn Benchmark Succeeded | Trace: `{trace_id}`")
    else:
        st.error(f"Benchmark could not complete: {result_data.get('error_message')}")
        return result_data

    # Prominent TTFA KPI Metrics Cards
    ttfa = result_data.get("ttfa_ms")
    mode = result_data.get("mode", "").upper()
    interceptions = result_data.get("interception_count", 0)
    violations = result_data.get("guardrail_violations", [])
    breakdown = result_data.get("breakdown") or {}
    total_ms = breakdown.get("total_turn_latency_ms", 0.0)

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        if ttfa is not None:
            # Color-coded latency categorization
            delta_color = "normal"
            if ttfa < 500:
                delta_str = "🟢 Ultra-fast (<500ms)"
            elif ttfa < 900:
                delta_str = "🟡 Standard (<900ms)"
            else:
                delta_str = "🔴 High Latency (>900ms)"

            st.metric(
                label="Time-to-First-Audio (TTFA)",
                value=f"{ttfa:.1f} ms",
                delta=delta_str,
            )
        else:
            st.metric(label="Time-to-First-Audio", value="N/A")

    with m2:
        st.metric(
            label="Voice pipeline",
            value=mode,
            delta="Selected architecture",
        )

    with m3:
        st.metric(
            label="Total Turn Latency",
            value=f"{total_ms:.1f} ms" if total_ms else "N/A",
            delta="End-to-End Playback",
        )

    with m4:
        st.metric(
            label="Policy checks",
            value=str(interceptions),
            delta=f"{len(violations)} Violations" if violations else "Policy Compliant",
        )

    # Transcript & Agent Response balloons
    st.markdown("#### Inside the conversation")
    chat_col1, chat_col2 = st.columns(2)

    with chat_col1:
        with st.chat_message("user"):
            st.write(f"**User Audio:** {result_data.get('transcription') or 'Speech audio input'}")

    with chat_col2:
        with st.chat_message("assistant"):
            st.write(f"**Synthesized Response:** {result_data.get('response_text') or 'No response captured'}")

    return result_data
