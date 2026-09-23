"""Streamlit component: Guardrail audit ledger and benchmark trace history."""
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
import streamlit as st


def render_audit_ledger(backend_url: str, active_result: Optional[Dict[str, Any]]) -> None:
    """
    Renders policy audit ledger and recent trace history.
    """
    st.markdown("### 🛡️ Guardrail Audit Ledger & Observability History")

    # If active result has violations or sidecar activity, show detailed card
    if active_result and active_result.get("interception_count", 0) > 0:
        violations = active_result.get("guardrail_violations", [])
        interceptions = active_result.get("interception_count", 0)
        breakdown = active_result.get("breakdown") or {}
        overhead = breakdown.get("guardrail_overhead_ms") or 0.0

        with st.expander("🔍 Active Trace Guardrail Evaluation Details", expanded=True):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                st.write(f"**Total Interceptions:** `{interceptions}`")
            with ec2:
                st.write(f"**Deterministic Overhead:** `{overhead:.2f} ms`")
            with ec3:
                status_badge = "❌ VIOLATION BLOCKED" if violations else "✅ POLICY PASSED"
                st.write(f"**Policy Outcome:** {status_badge}")

            if violations:
                st.error("Detected Policy Breaches:")
                for v in violations:
                    st.markdown(f"- ⚠️ {v}")
            else:
                st.success("All intercepted function calls complied with clinic rules and schema contracts.")

    # Recent Benchmark History Table
    st.markdown("#### 📜 Recent Observability Run History")
    recent_runs: List[Dict[str, Any]] = []

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(f"{backend_url}/v1/telemetry/history/recent?limit=15")
            if resp.status_code == 200:
                recent_runs = resp.json()
    except Exception as e:
        st.warning(f"Could not load recent history from backend: {e}")

    if not recent_runs:
        st.caption("No historical benchmarks recorded yet in Supabase/Outbox store.")
        return

    table_data = []
    for r in recent_runs:
        violations = r.get("guardrail_violations") or []
        outcome = "FAIL (Blocked)" if violations else "PASS (Compliant)"
        ttfa = r.get("ttfa_ms")
        ttfa_str = f"{ttfa:.1f} ms" if ttfa is not None else "N/A"

        table_data.append({
            "Trace ID": r.get("trace_id", "")[:12] + "...",
            "Mode": r.get("mode", "").upper(),
            "TTFA": ttfa_str,
            "Interceptions": r.get("interception_count", 0),
            "Guardrail Policy": outcome,
            "Status": r.get("status", "").upper(),
            "Timestamp": (r.get("completed_at") or "")[:19].replace("T", " "),
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
