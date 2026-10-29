# VoiceOps operations & evaluation

## Architecture comparison lab

The public root serves the general-purpose architecture lab. Choose a task, use a sample,
record once or upload a WAV, then compare buffered, streaming, guarded and isolated text/audio buffering paths.
Reference material, an optional expected phrase, and sandbox action policies are configurable.
Results include measured server event timelines and browser trial-ready-to-scheduled-playback
latency. Initial WAV upload and physical speaker output are excluded. JSON/CSV exports retain
input hashes, configuration, responses and failures. History is held only in the current tab.

Use `python scripts/start_render.py` for the combined service. The public gateway and private API share provider imports in one process. The gateway runs on
`PORT` (default 10000); Streamlit uses loopback 8501 with base path `/studio`; the earlier API
uses loopback 8000. `/health` and `/_stcore/health` on the gateway support Render health checks.
The gateway exposes the bounded experiment channel and existing studio; the legacy API is private.
Two experiments can run concurrently, with up to 30 repetitions per selected mode plus optional excluded warm-ups.

Run `python scripts/evaluate_architectures.py --url ws://localhost:10000/lab/ws` for live
server comparisons; add `--task action --audio frontend/lab/action.wav` to inspect policy
blocking of an over-limit simulated refund. These reports do not measure browser playback.
Use the browser for playback acceptance tests. A few trials do not establish architectural
speedup percentages. See ARCHITECTURE_LAB.md for the complete measurement contract.

## General conversation workspace

Open **Conversation** on the public root. Configure instructions and optional reference material, then
start the microphone once. Captured speech interrupts a reply; a short pause submits a complete turn.
Use headphones. Sound check lets you select an input, check its level and play a local speaker tone; permission errors explain how to recover. Stop reply and End conversation are always available during a session.
Try sample conversation sends two prerecorded requests through live providers and demonstrates context.
The readiness indicator reports server/configuration state, with providers verified during use.
Evaluation suite runs eight varied synthetic requests and exports partial or completed reports. Session runs includes suite and comparison history, JSON imports and compatible release comparisons. Opt-in browser saving excludes audio. The field guide describes the literal checker and measurement limits.
See ARCHITECTURE_LAB.md for the protocol, limits and measurement boundaries.

## Legacy booking voice calls

Open **/studio/ → Live call**, choose **Start call**, and allow microphone access once. Speak naturally;
a roughly 1.1-second pause submits the utterance automatically. The reply plays and listening
resumes without pressing Record or Send. Mute and End remain available. Listening pauses
while the assistant speaks to avoid echo; interruption/barge-in is not supported.
Microphone audio is processed by Groq; reply text is synthesized by Edge-TTS.
The browser mutes when hidden and after five minutes without a turn. End and navigation
release microphone tracks. A blocked browser audio context exposes a Play & continue button.

**Try a sample conversation** uses two prerecorded fictional voices through the same pause
detector, server bridge, live providers, and playback loop. It does not test physical microphones.
The component has no API keys and uses Streamlit's existing connection; the backend stays private.

The call uses the existing Pipecat engine. Groq tool calls enter the deterministic
guardrail callback; the tool result returns through the assistant context aggregator
before the next answer. Conversation context retains returned booking IDs so a caller
can say “cancel that appointment.” Each call has an isolated in-memory booking store.
These are demo mutations, not appointments in an external clinic system.

## Reliability contract

- 16 kHz, mono, 16-bit PCM WAV; 0.1–30 seconds per recording; automatic microphone segments cap at 25 seconds.
- 60-second pipeline deadline; one turn per call; two concurrent turns per process.
- Maximum 24 sessions, 12 turns per session, 30-minute idle expiry.
- Turn IDs are idempotent within the session. Reusing an ID with different audio is rejected.
- Automatic retries never repeat booking tools. A failed speech response can follow a
  successful booking mutation; inspect the returned booking list before trying again.
- End call removes the session. Abandoned sessions expire and are pruned when new calls
  are created. Only the latest reply audio is cached; raw input files are deleted after each turn.
- Calls are excluded from shared benchmark history. Provider logs may still contain
  conversational data; use fictional details. No production identity or authorization model is provided.
- The combined Render launcher waits for API health, then starts Streamlit and the public lab gateway.
  It exits if any child process fails. Free-instance sleep and restart discard all in-memory state.

## Debugging

Use the trace ID in **Turn diagnostics** to correlate Render logs. Check model availability,
Groq quota, Edge-TTS connectivity, and the request audio format. Never paste API keys,
phone numbers, or full customer transcripts into public issues. Report sanitized failures.

`/_stcore/health` is the public dashboard health endpoint. `/health` on loopback port 8000
checks the API process. Neither endpoint proves provider availability. A completed live
voice evaluation is the provider-level check.

## Evaluation

Run deterministic tests with `pytest -q`. Start the backend, configure `GROQ_API_KEY`, then run:

```bash
python scripts/evaluate_voice.py --base-url http://127.0.0.1:8000
```

This opt-in command uses live provider quota. Edge-TTS generates synthetic test requests;
Groq transcribes and reasons over them. Assertions inspect actual booking state, tool
counts, completed audio, cancellation state, and duplicate-turn behavior. Results contain
trace IDs and timings, not keys or full transcripts. It deletes its isolated call afterward.

The public Render API is deliberately loopback-only. To test the deployed application,
use **Live call → Try a sample conversation** and inspect both turns and Booking activity.
For a human microphone acceptance test, select **Start call**, speak a request, pause, hear
the reply, and speak the follow-up without touching the controls. Confirm mute/end, permission
denial, and the correct input/output device. Synthetic tests do not establish microphone quality.
Run the client turn-boundary checks with `node --test tests/audio-turns.test.mjs`.

Measure TTFA separately from full turn duration. TTFA starts at the backend speech-end
marker and ends at first generated audio; upload and browser playback add latency.
The current implementation returns the completed audio file, not a streaming playback buffer.

## Release checks

1. Run unit tests and opt-in live evaluation.
2. Inspect the staged diff for secrets; `.env` and `.venv` stay ignored.
3. Push `codex/render-deploy`, then deploy that commit in Render (free plan).
4. Confirm health, microphone controls, reference tabs, a completed voice turn, and booking state.
5. Record any untested browser/device behavior explicitly.
