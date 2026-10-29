"""Bounded public experiment protocol, without live provider calls."""
import base64
import pytest
from backend.application.services.usage_budget import UsageBudget
from fastapi.testclient import TestClient
from backend.lab_server import app
from tests.unit.pipelines.test_architecture_lab import wav


@pytest.fixture(autouse=True)
def isolated_budget(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.lab_server.usage_budget", UsageBudget(str(tmp_path / "usage.sqlite")))


def test_public_lab_protocol_and_private_api_boundary(monkeypatch):
    async def fake(spec, mode, audio, emit):
        emit({"type": "stage", "name": "first_audio_generated", "ms": 1})
        emit({"type": "audio", "pcm": "AAA="})
        return {"mode": mode, "status": "completed", "metrics": {"server_first_audio_ms": 1}}
    monkeypatch.setattr("backend.lab_server.run_architecture", fake)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/v1/calls").status_code in (404, 405)
        with client.websocket_connect("/lab/ws") as ws:
            ws.send_json({"spec": {"modes": ["streaming"]}, "audio": base64.b64encode(wav()).decode()})
            assert ws.receive_json()["type"] == "accepted"
            assert ws.receive_json()["type"] == "run_start"
            ws.send_json({"type": "ready"})
            assert ws.receive_json()["type"] == "stage"
            assert ws.receive_json()["type"] == "audio"
            assert ws.receive_json()["status"] == "completed"
            ws.send_json({"type": "next"})
            assert ws.receive_json()["type"] == "complete"


def test_bad_configuration_returns_error(monkeypatch):
    with TestClient(app) as client:
        with client.websocket_connect("/lab/ws") as ws:
            ws.send_json({"spec": {"repeats": 100}, "audio": ""})
            assert ws.receive_json()["type"] == "error"


def test_quota_rejection_happens_before_provider_work(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.lab_server.usage_budget", UsageBudget(str(tmp_path / "closed.sqlite"), daily=0))
    async def forbidden(*args):
        raise AssertionError("Provider work must not start after quota rejection")
    monkeypatch.setattr("backend.lab_server.run_architecture", forbidden)
    with TestClient(app) as client:
        with client.websocket_connect("/lab/ws") as ws:
            ws.send_json({"spec": {"modes": ["streaming"]}, "audio": base64.b64encode(wav()).decode()})
            assert ws.receive_json()["code"] == "usage_limit"
