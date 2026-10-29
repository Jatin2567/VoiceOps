"""The browser call bridge retains retry identity and session state."""
from unittest.mock import Mock, patch
from frontend.components.handsfree import handle_event


def test_start_turn_duplicate_and_end():
    state = {}
    started = Mock(status_code=200)
    started.json.return_value = {"session_id": "room"}
    with patch("httpx.post", return_value=started) as post:
        event = {"event_id": "open", "kind": "start"}
        assert handle_event(event, "http://api", state)
        assert state["call_id"] == "room"
        assert not handle_event(event, "http://api", state)
        assert post.call_count == 1
    turn = {"turn_id": "turn", "status": "completed", "bookings": [{"status": "confirmed"}], "audio_base64": "wav"}
    response = Mock(status_code=200)
    response.json.return_value = turn
    with patch("httpx.post", return_value=response) as post:
        event = {"event_id": "request", "kind": "turn", "turn_id": "turn", "audio_base64": "input"}
        handle_event(event, "http://api", state)
        assert state["call_bookings"] == turn["bookings"]
        event["event_id"] = "retry"
        handle_event(event, "http://api", state)
        assert len(state["call_turns"]) == 1
        assert post.call_args.kwargs["json"]["turn_id"] == "turn"
    with patch("httpx.delete", return_value=Mock(status_code=200)):
        handle_event({"event_id": "end", "kind": "end"}, "http://api", state)
        assert "call_id" not in state
        assert state["call_bookings"]  # Final outcome stays reviewable.


def test_lost_response_can_retry_without_new_turn_identity():
    import httpx
    state = {"call_id": "room"}
    with patch("httpx.post", side_effect=httpx.ReadTimeout("test")):
        handle_event({"event_id": "request", "kind": "turn", "turn_id": "same", "audio_base64": "wav"}, "http://api", state)
    assert state["call_component_result"]["retryable"] is True
