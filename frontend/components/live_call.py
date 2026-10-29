"""Voice studio: recording, contextual replies, and transparent booking actions."""
import base64
from frontend.components.handsfree import render_handsfree
from datetime import datetime, timedelta, timezone
import streamlit as st


def render_live_call(backend_url, online):
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown('''<section class="studio-intro">
        <div class="eyebrow"><span class="tiny-wave">▥</span> THE VOICE STUDIO / 01</div>
        <h1>Good conversations.<br><em>Real actions.</em></h1>
        <p class="intro-copy">A voice that listens. An assistant that follows through.<br>Book, check, and cancel—with policies built into every turn.</p>
        <div class="studio-tags"><span>Groq × Edge-TTS</span><span>Hybrid guardrails</span></div>
        </section>''', unsafe_allow_html=True)
        example_date = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%B %d, %Y")
        st.markdown('<div class="prompt-label">SOMETHING TO SAY</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sample-prompt">“Book a consultation for Alex Test on {example_date} at 10 AM UTC. My number is 9876543210.”</div>', unsafe_allow_html=True)
        st.caption('Then try “Cancel the appointment you just booked.” Use fictional details and UTC times.')
    with right:
        with st.container(border=True, key="voice_console"):
            st.markdown('<div class="console-top"><span>VOICEOPS ASSISTANT</span><span class="console-status">HANDS-FREE CONVERSATION</span></div>', unsafe_allow_html=True)
            render_handsfree(backend_url, online)

    st.markdown('<div class="process-strip"><div><b>01</b><span>Speak naturally<small>Start once · pause to finish a turn</small></span></div><div><b>02</b><span>Policies come first<small>Every booking action is checked</small></span></div><div><b>03</b><span>Hear the outcome<small>Spoken replies, visible actions</small></span></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><span class="eyebrow">YOUR SESSION</span><h2>Every word. Every action.</h2></div>', unsafe_allow_html=True)
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        st.markdown('<div class="panel-label">CONVERSATION</div>', unsafe_allow_html=True)
        if not st.session_state.get("call_turns"):
            st.markdown('<div class="conversation-empty"><span>“</span><h3>A little quiet, for now.</h3><p>Your words and the assistant’s replies will appear here.<br>Start a conversation above to make the first move.</p></div>', unsafe_allow_html=True)
        for turn in st.session_state.get("call_turns", [])[-6:]:
            with st.chat_message("user"):
                st.write(turn.get("transcription") or "Voice recording")
            with st.chat_message("assistant"):
                if turn["status"] == "completed":
                    st.write(turn["response_text"])
                    if turn.get("audio_base64"):
                        st.audio(base64.b64decode(turn["audio_base64"]), format="audio/wav", autoplay=False)
                    st.caption(f"{turn['interception_count']} tool checks · first generated audio {turn['ttfa_ms'] / 1000:.1f}s · trace {turn['trace_id'][:8]}")
                else:
                    st.error(turn["error_message"])
                for violation in turn["guardrail_violations"]:
                    st.warning(violation)
                with st.expander("Turn diagnostics"):
                    st.json({k: turn.get(k) for k in ["trace_id", "status", "ttfa_ms", "breakdown", "interception_count", "guardrail_violations"]})
    with right:
        with st.container(border=True):
            st.subheader("Booking activity")
            bookings = st.session_state.get("call_bookings", [])
            if not bookings:
                st.caption("Confirmed appointments will appear here. Nothing has been booked yet.")
            for booking in bookings:
                st.markdown(f"**{booking['service_type'].replace('_', ' ').title()} · {booking['status'].title()}**")
                st.write(booking["slot_time"])
                st.caption(f"{booking['customer_name']} · ID {booking['id']}")

        with st.expander("Session details & privacy"):
            st.write("Hands-free demo with automatic pause detection. Listening pauses during replies; this is not full-duplex telephony. Bookings exist only in your session and disappear on restart. Calls expire after 30 idle minutes, with up to 12 turns. Microphone access requires HTTPS and browser permission.")
            st.caption("If autoplay is blocked, use the audio player. The Reference page explains recovery, policies, and evaluation.")
