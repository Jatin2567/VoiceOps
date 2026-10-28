"""Groq speech recognition and reasoning, guarded clinic tools, and Edge-TTS."""
from backend.pipelines.modes.cascade_topology import build_cascade_pipeline
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor


def build_hybrid_pipeline(trace_id, queue_publisher, guardrail_service, system_instruction=None):
    interceptor = DeterministicSidecarInterceptor(
        trace_id=trace_id, guardrail_service=guardrail_service, callback_driven=True,
    )
    pipeline, telemetry = build_cascade_pipeline(
        trace_id, queue_publisher, interceptor=interceptor, system_instruction=system_instruction,
    )
    return pipeline, telemetry, interceptor
