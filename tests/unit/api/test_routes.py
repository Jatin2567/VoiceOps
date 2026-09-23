"""Unit tests for FastAPI endpoints (Benchmark, Telemetry, WebSockets)."""
import unittest

from fastapi.testclient import TestClient

from backend.main import app


class TestFastAPIRoutes(unittest.TestCase):
    """Test suite ensuring FastAPI driving endpoints satisfy system requirements."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        """Verify GET /health returns healthy status."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "VoiceOps Backend")

    def test_list_modes(self):
        """Verify GET /v1/benchmark/modes lists all three topologies."""
        resp = self.client.get("/v1/benchmark/modes")
        self.assertEqual(resp.status_code, 200)
        modes = resp.json()
        self.assertEqual(len(modes), 3)
        mode_ids = [m["id"] for m in modes]
        self.assertIn("cascade", mode_ids)
        self.assertIn("native", mode_ids)
        self.assertIn("hybrid", mode_ids)

    def test_trigger_benchmark_instant_return(self):
        """
        CRITICAL (Directive 2): Verify POST /v1/benchmark returns instantly
        with a valid trace_id and 200 OK.
        """
        payload = {
            "mode": "cascade",
            "scenario_name": "API Test",
        }
        resp = self.client.post("/v1/benchmark", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("trace_id", data)
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["mode"], "cascade")

    def test_telemetry_get_recent_history(self):
        """Verify GET /v1/telemetry/history/recent returns recent records."""
        resp = self.client.get("/v1/telemetry/history/recent?limit=5")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_websocket_streaming_handshake(self):
        """Verify WebSocket endpoint connects and emits initial handshake message."""
        with self.client.websocket_connect("/ws/v1/stream/session_test_123") as ws:
            data = ws.receive_json()
            self.assertEqual(data["event"], "connected")
            self.assertEqual(data["session_id"], "session_test_123")


if __name__ == "__main__":
    unittest.main()
