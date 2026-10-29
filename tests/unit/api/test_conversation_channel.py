import asyncio
import base64
import pytest
from fastapi.testclient import TestClient
from backend.lab_server import app
from backend.application.services.usage_budget import UsageBudget
from tests.unit.pipelines.test_architecture_lab import wav


@pytest.fixture(autouse=True)
def budget(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.lab_server.usage_budget', UsageBudget(str(tmp_path / 'usage.sqlite')))


def test_readiness_does_not_reserve_or_claim_provider_verification(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    with TestClient(app) as client:
        a = client.get('/api/readiness').json()
        b = client.get('/api/readiness').json()
        assert a['configured'] is True
        assert a['provider_verified'] is False
        assert a['quota'] == b['quota']


def test_followup_receives_completed_context(monkeypatch):
    histories = []
    async def fake(spec, mode, audio, emit, history=None):
        histories.append(history)
        return {'status': 'completed', 'transcript': 'Question', 'response': 'Answer'}
    monkeypatch.setattr('backend.lab_server.run_architecture', fake)
    with TestClient(app) as client, client.websocket_connect('/conversation/ws') as ws:
        ws.send_json({'spec': {}})
        assert ws.receive_json()['type'] == 'ready'
        for _ in range(2):
            ws.send_json({'type': 'audio', 'audio': base64.b64encode(wav()).decode()})
            assert ws.receive_json()['type'] == 'turn_start'
            assert ws.receive_json()['type'] == 'result'
    assert histories == [[], [{'role': 'user', 'content': 'Question'}, {'role': 'assistant', 'content': 'Answer'}]]


def test_interrupt_cancels_work_and_omits_stale_history(monkeypatch):
    cancelled, histories = [], []
    async def fake(spec, mode, audio, emit, history=None):
        histories.append(history)
        if len(histories) == 1:
            emit({'type': 'stage', 'name': 'started', 'ms': 1})
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        return {'status': 'completed', 'transcript': 'Fresh question', 'response': 'Fresh answer'}
    monkeypatch.setattr('backend.lab_server.run_architecture', fake)
    with TestClient(app) as client, client.websocket_connect('/conversation/ws') as ws:
        ws.send_json({'spec': {}})
        ws.receive_json()
        payload = {'type': 'audio', 'audio': base64.b64encode(wav()).decode()}
        ws.send_json(payload)
        ws.receive_json()
        assert ws.receive_json()['name'] == 'started'
        ws.send_json({'type': 'interrupt', 'turn_id': 1})
        assert ws.receive_json()['type'] == 'interrupted'
        ws.send_json(payload)
        assert ws.receive_json()['turn_id'] == 2
        assert ws.receive_json()['response'] == 'Fresh answer'
    assert cancelled == [True]
    assert histories == [[], []]


def test_conversation_rejects_cross_origin():
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect('/conversation/ws', headers={'origin':'https://unrelated.example'}):
                pass
