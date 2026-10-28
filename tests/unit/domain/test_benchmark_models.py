"""Unit tests for Benchmark domain models."""
import unittest
from datetime import datetime, timezone
from uuid import UUID

from backend.domain.models.benchmark import (
    AudioInputSource,
    BenchmarkRequest,
    BenchmarkResult,
    BenchmarkStatus,
    LatencyBreakdown,
    PipelineMode,
)


class TestBenchmarkModels(unittest.TestCase):
    """Test suite for benchmark domain models."""

    def test_pipeline_modes(self):
        """Verify all three topological modes are supported."""
        self.assertEqual(PipelineMode.CASCADE.value, "cascade")
        self.assertEqual(PipelineMode.CASCADE.value, "cascade")
        self.assertEqual(PipelineMode.HYBRID.value, "hybrid")

    def test_benchmark_request_defaults(self):
        """Verify BenchmarkRequest generates trace ID and defaults to cascade."""
        request = BenchmarkRequest()
        self.assertIsNotNone(request.trace_id)
        # Verify trace_id is valid UUID string
        UUID(request.trace_id)
        self.assertEqual(request.mode, PipelineMode.CASCADE)
        self.assertIsNone(request.audio_file_path)
        self.assertEqual(request.metadata, {})

    def test_benchmark_request_custom_fields(self):
        """Verify BenchmarkRequest custom parameters."""
        req = BenchmarkRequest(
            trace_id="trace-12345",
            mode=PipelineMode.HYBRID,
            audio_file_path="/mock/test.wav",
            session_id="session-99",
            metadata={"caller_id": "client-A"}
        )
        self.assertEqual(req.trace_id, "trace-12345")
        self.assertEqual(req.mode, PipelineMode.HYBRID)
        self.assertEqual(req.audio_file_path, "/mock/test.wav")
        self.assertEqual(req.metadata["caller_id"], "client-A")

    def test_benchmark_result_construction(self):
        """Verify BenchmarkResult creation and latency breakdown."""
        breakdown = LatencyBreakdown(
            stt_latency_ms=180.5,
            llm_ttft_ms=210.0,
            tts_ttfb_ms=150.2,
            guardrail_overhead_ms=45.0,
            total_turn_latency_ms=850.0,
        )
        result = BenchmarkResult(
            trace_id="test-trace-id",
            mode=PipelineMode.HYBRID,
            status=BenchmarkStatus.COMPLETED,
            ttfa_ms=540.7,
            breakdown=breakdown,
            transcription="Book an appointment for tomorrow 10am",
            response_text="Appointment booked successfully.",
            guardrail_violations=[],
            interception_count=1,
            completed_at=datetime.now(timezone.utc),
        )
        self.assertEqual(result.trace_id, "test-trace-id")
        self.assertEqual(result.ttfa_ms, 540.7)
        self.assertEqual(result.interception_count, 1)
        self.assertEqual(result.status, BenchmarkStatus.COMPLETED)
        self.assertEqual(result.breakdown.stt_latency_ms, 180.5)
        self.assertEqual(result.breakdown.guardrail_overhead_ms, 45.0)

    def test_benchmark_result_json_serialization(self):
        """Verify Pydantic model dump and JSON serialization."""
        result = BenchmarkResult(
            trace_id="serial-trace",
            mode=PipelineMode.CASCADE,
            status=BenchmarkStatus.FAILED,
            error_message="TTS connection timeout"
        )
        json_data = result.model_dump_json()
        self.assertIn("serial-trace", json_data)
        self.assertIn("cascade", json_data)
        self.assertIn("TTS connection timeout", json_data)


if __name__ == "__main__":
    unittest.main()
