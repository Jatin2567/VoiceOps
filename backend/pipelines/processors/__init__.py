"""Pipecat custom frame processors module export."""
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor
from backend.pipelines.processors.vad_processor import create_vad_processor

__all__ = [
    "TelemetryProcessor",
    "DeterministicSidecarInterceptor",
    "create_vad_processor",
]
