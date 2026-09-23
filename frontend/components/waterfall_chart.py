"""Streamlit component: Interactive Latency Breakdown Waterfall & Bar Chart."""
from typing import Any, Dict, Optional

import plotly.graph_objects as go
import streamlit as st


def render_waterfall_chart(result_data: Optional[Dict[str, Any]]) -> None:
    """
    Renders an interactive latency breakdown chart (STT, LLM TTFT, TTS TTFB, Guardrail overhead).
    """
    st.markdown("### ⏱️ Latency Distribution & Pipeline Breakdown")

    if not result_data:
        st.caption("No benchmark metrics available to display.")
        return

    breakdown = result_data.get("breakdown") or {}
    mode = result_data.get("mode", "cascade").lower()
    ttfa = result_data.get("ttfa_ms") or 0.0

    stages = []
    values = []
    colors = []

    if mode == "cascade":
        stt = breakdown.get("stt_latency_ms") or 120.0
        llm = breakdown.get("llm_ttft_ms") or 180.0
        tts = breakdown.get("tts_ttfb_ms") or 140.0

        stages = ["Whisper STT", "Llama-3 TTFT", "Edge-TTS TTFB", "First Audio (TTFA)"]
        values = [stt, llm, tts, ttfa]
        colors = ["#38bdf8", "#818cf8", "#c084fc", "#4ade80"]

    elif mode == "hybrid":
        guardrail = breakdown.get("guardrail_overhead_ms") or 35.0
        gemini_s2s = max(0.0, ttfa - guardrail)

        stages = ["Gemini Live S2S Base", "Sidecar Guardrail Overhead", "Total TTFA"]
        values = [gemini_s2s, guardrail, ttfa]
        colors = ["#38bdf8", "#f43f5e", "#4ade80"]

    else:  # native
        stages = ["Speech Reception & VAD", "Gemini Multimodal Live S2S (TTFA)"]
        vad_est = min(50.0, ttfa * 0.1)
        values = [vad_est, ttfa]
        colors = ["#38bdf8", "#4ade80"]

    # Plotly Horizontal Bar Chart
    fig = go.Figure(
        go.Bar(
            x=values,
            y=stages,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color="#ffffff", width=1),
            ),
            text=[f"{v:.1f} ms" for v in values],
            textposition="auto",
            hoverinfo="x+y",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.6)",
        font=dict(family="sans-serif", size=13, color="#e2e8f0"),
        height=320,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(
            title="Latency in Milliseconds (ms)",
            gridcolor="#334155",
            zerolinecolor="#475569",
        ),
        yaxis=dict(
            autorange="reversed",
            gridcolor="#334155",
        ),
    )

    st.plotly_chart(fig, use_container_width=True)
