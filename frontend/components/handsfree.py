"""Server bridge for the persistent browser audio component; credentials stay server-side."""
from pathlib import Path
import httpx
import streamlit as st
import streamlit.components.v1 as components

conversation = components.declare_component("voiceops_conversation", path=str(Path(__file__).with_name("conversation")))


def handle_event(event, backend_url, state):
    """Handle each browser event once; retries retain the original tool-safe turn ID."""
    if not isinstance(event, dict) or not event.get("event_id") or event["event_id"] == state.get("call_event"):
        return False
    state["call_event"] = event["event_id"]
    result = {"event_id": event["event_id"], "kind": event.get("kind")}
    sid = state.get("call_id")
    try:
        if event.get("kind") == "start":
            if sid and event.get("fresh"):
                ended = httpx.delete(f"{backend_url}/v1/calls/{sid}", timeout=10)
                ended.raise_for_status()
                sid = None
            if not sid:
                response = httpx.post(backend_url + "/v1/calls", timeout=10)
                response.raise_for_status()
                state.update(call_id=response.json()["session_id"], call_turns=[], call_bookings=[])
        elif event.get("kind") == "turn" and sid:
            audio = event.get("audio_base64", "")
            if not isinstance(audio, str) or len(audio) > 1280060:
                raise ValueError("Please keep each spoken turn under 25 seconds.")
            response = httpx.post(f"{backend_url}/v1/calls/{sid}/turns", json={
                "turn_id": event.get("turn_id"), "audio_base64": audio,
            }, timeout=80)
            if response.status_code != 200:
                result.update(error=response.json().get("detail", "The turn could not complete."), retryable=response.status_code in (409, 503))
            else:
                turn = response.json()
                turns = state.get("call_turns", [])
                if not any(t["turn_id"] == turn["turn_id"] for t in turns):
                    for previous in turns:
                        previous["audio_base64"] = None
                    turns.append(turn)
                state.update(call_turns=turns, call_bookings=turn["bookings"])
                result.update(turn)
        elif event.get("kind") == "end":
            if sid:
                response = httpx.delete(f"{backend_url}/v1/calls/{sid}", timeout=10)
                if response.status_code not in (200, 404):
                    response.raise_for_status()
            state.pop("call_id", None)
        else:
            result["error"] = "Start a new call to continue."
    except httpx.HTTPError:
        result.update(error="Connection interrupted. Retry this turn to retrieve its original result safely.", retryable=event.get("kind") == "turn")
    except ValueError as exc:
        result["error"] = str(exc)
    state["call_component_result"] = result
    return True


def render_handsfree(backend_url, online):
    event = conversation(session_id=st.session_state.get("call_id"),
                         result=st.session_state.get("call_component_result"), online=online,
                         key="handsfree_console", default=None)
    if handle_event(event, backend_url, st.session_state):
        st.rerun()
