"""Streamlit component: Interactive Latency Breakdown Waterfall & Bar Chart."""
from typing import Any, Dict, Optional

import plotly.graph_objects as go
import streamlit as st


def render_waterfall_chart(result_data: Optional[Dict[str, Any]]) -> None:
    """
    Renders an interactive latency breakdown chart (STT, LLM TTFT, TTS TTFB, Guardrail overhead).
    """
    st.markdown("### Where the time goes")

    if not result_data:
        st.caption("No benchmark metrics available to display.")
        return

    breakdown = result_data.get("breakdown") or {}
    mode = result_data.get("mode", "cascade").lower()
    ttfa = result_data.get("ttfa_ms") or 0.0

    stages = []
    values = []
    colors = []

    for key, label, color in [
        ("stt_latency_ms", "Whisper STT", "#bdabdf"),
        ("llm_ttft_ms", "Groq first token", "#e4bb7a"),
        ("tts_ttfb_ms", "Edge-TTS first audio", "#e78360"),
        ("guardrail_overhead_ms", "Guardrail checks", "#c68c79"),
    ]:
        if breakdown.get(key) is not None:
            stages.append(label)
            values.append(breakdown[key])
            colors.append(color)
    stages.append("First audio (TTFA)")
    values.append(ttfa)
    colors.append("#ff784f")

    # Plotly Horizontal Bar Chart
    fig = go.Figure(
        go.Bar(
            x=values,
            y=stages,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(width=0),
            ),
            text=[f"{v:.1f} ms" for v in values],
            textposition="auto",
            hoverinfo="x+y",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="sans-serif", size=13, color="#c5c0b6"),
        height=320,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(
            title="Latency in Milliseconds (ms)",
            gridcolor="#34312c",
            zerolinecolor="#4c463e",
        ),
        yaxis=dict(
            autorange="reversed",
            gridcolor="#34312c",
        ),
    )

    st.caption("Reported timing values only. Unavailable stages are omitted; stages may overlap.")
    st.plotly_chart(fig, use_container_width=True)
