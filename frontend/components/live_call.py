"""Accessible browser microphone turns with spoken replies and visible policy outcomes."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
import streamlit as st


def render_live_call(backend_url, online):
    st.markdown('''<section class="call-hero"><div class="eyebrow">VOICE WORKSPACE / LIVE CALL</div>
    <h1>A conversation.<br><span>With clear boundaries.</span></h1>
    <p>Speak naturally. Check availability, book a visit, or cancel an appointment.
    Every action passes through the same clinic policies.</p>
    <div class="pill-row"><span>Groq intelligence</span><span>Edge-TTS voice</span><span>Hybrid guardrails</span></div></section>''', unsafe_allow_html=True)
    st.caption("Demo clinic • isolated bookings • UTC appointment times • push-to-talk, not a phone call")
    sid = st.session_state.get("call_id")
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Your call room")
            if not sid:
                st.write("Start a call, allow microphone access, then record a short request. Stop recording and send your turn to hear the assistant.")
                st.info("Audio is sent to Groq for transcription and reasoning. Reply text is sent to Microsoft Edge-TTS. Use fictional booking details.")
                if st.button("Start voice call", type="primary", disabled=not online, width="stretch"):
                    try:
                        response = httpx.post(backend_url + "/v1/calls", timeout=10)
                        response.raise_for_status()
                        st.session_state.update(call_id=response.json()["session_id"], call_turns=[], call_bookings=[], call_pending=None, call_recorder=0)
                        st.rerun()
                    except httpx.HTTPError:
                        st.error("Could not open a call. The server may be waking up; try again shortly.")
            else:
                st.success("Call ready · Hybrid policies active")
                source = st.radio("Voice input", ["Microphone", "Test recording"], horizontal=True)
                if source == "Microphone":
                    audio = st.audio_input("Record your request", sample_rate=16000,
                                           key=f"call_mic_{st.session_state.call_recorder}")
                    st.caption("Record → stop → send. Keep each turn under 30 seconds. If microphone access is denied, enable it in your browser’s site settings.")
                else:
                    audio = st.file_uploader("Upload a 16 kHz mono WAV", type="wav", key=f"call_upload_{st.session_state.call_recorder}")
                if st.button("Send voice turn", type="primary", disabled=audio is None, width="stretch"):
                    raw = audio.getvalue()
                    if len(raw) > 960044:
                        st.error("This recording is too long. Record less than 30 seconds.")
                    else:
                        digest = hashlib.sha256(raw).hexdigest()
                        pending = st.session_state.get("call_pending")
                        if not pending or pending[0] != digest:
                            pending = (digest, str(uuid4()))
                            st.session_state.call_pending = pending
                        with st.status("Listening, checking policies, and preparing your reply…", expanded=True) as progress:
                            st.write("Your recording is being processed. Please wait before sending another turn.")
                            try:
                                response = httpx.post(f"{backend_url}/v1/calls/{sid}/turns", json={
                                    "turn_id": pending[1], "audio_base64": base64.b64encode(raw).decode(),
                                }, timeout=80)
                                if response.status_code != 200:
                                    st.error(response.json().get("detail", "The call could not process this turn."))
                                    progress.update(label="Turn not completed", state="error")
                                else:
                                    result = response.json()
                                    if not any(t["turn_id"] == result["turn_id"] for t in st.session_state.call_turns):
                                        # Keep previous text while releasing old audio from browser session memory.
                                        for prior in st.session_state.call_turns:
                                            prior["audio_base64"] = None
                                        st.session_state.call_turns.append(result)
                                    st.session_state.call_bookings = result["bookings"]
                                    st.session_state.call_pending = None
                                    st.session_state.call_recorder += 1
                                    st.session_state.call_autoplay = result["turn_id"]
                                    st.rerun()
                            except httpx.HTTPError:
                                st.error("Connection interrupted. Send the same recording again to retrieve its result without repeating the booking action.")
                                progress.update(label="Connection interrupted", state="error")
                if st.button("End call & clear session", width="stretch"):
                    try:
                        response = httpx.delete(f"{backend_url}/v1/calls/{sid}", timeout=10)
                        if response.status_code not in (200, 404):
                            st.error("A reply is still in progress. Wait for it to finish, then end the call.")
                        else:
                            for key in list(st.session_state):
                                if key.startswith("call_"):
                                    del st.session_state[key]
                            st.rerun()
                    except httpx.HTTPError:
                        st.error("Could not reach the server to end the call. Please try again.")
        for turn in st.session_state.get("call_turns", [])[-6:]:
            with st.chat_message("user"):
                st.write(turn.get("transcription") or "Voice recording")
            with st.chat_message("assistant"):
                if turn["status"] == "completed":
                    st.write(turn["response_text"])
                    if turn.get("audio_base64"):
                        auto = st.session_state.get("call_autoplay") == turn["turn_id"]
                        st.audio(base64.b64decode(turn["audio_base64"]), format="audio/wav", autoplay=auto)
                        st.session_state.call_autoplay = None
                    st.caption(f"{turn['interception_count']} tool checks · first generated audio {turn['ttfa_ms'] / 1000:.1f}s · trace {turn['trace_id'][:8]}")
                else:
                    st.error(turn["error_message"])
                for violation in turn["guardrail_violations"]:
                    st.warning(violation)
                with st.expander("Turn diagnostics"):
                    st.json({k: turn.get(k) for k in ["trace_id", "status", "ttfa_ms", "breakdown", "interception_count", "guardrail_violations"]})
    with right:
        with st.container(border=True):
            st.subheader("Try a conversation")
            example_date = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%B %d, %Y")
            st.write(f'“Book a consultation for Alex Test on {example_date} at 10 AM UTC. My number is 9876543210.”')
            st.write('Then: “Cancel the appointment you just booked.”')
            st.caption("Use a future date. The assistant remembers tool results within this call, including the booking ID.")
        with st.container(border=True):
            st.subheader("Booking activity")
            bookings = st.session_state.get("call_bookings", [])
            if not bookings:
                st.caption("Confirmed appointments will appear here. Nothing has been booked yet.")
            for booking in bookings:
                st.markdown(f"**{booking['service_type'].replace('_', ' ').title()} · {booking['status'].title()}**")
                st.write(booking["slot_time"])
                st.caption(f"{booking['customer_name']} · ID {booking['id']}")
        with st.container(border=True):
            st.subheader("What keeps this reliable")
            st.write("Policy checks happen before a booking action. Duplicate sends reuse the original result. Failed turns show an error instead of invented audio.")
            st.caption("Calls expire after 30 idle minutes or a server restart. Up to 12 turns per call. Audio playback may require pressing Play in your browser.")
