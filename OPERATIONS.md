# VoiceOps operations & evaluation

## Browser voice calls

Open **Live call**, choose **Start voice call**, allow microphone access, record a short
request, stop, and send the turn. The reply has an audio player and a transcript.
This is push-to-talk on HTTPS, not telephone connectivity or full-duplex streaming.
Microphone audio is processed by Groq; reply text is synthesized by Edge-TTS.

The call uses the existing Pipecat engine. Groq tool calls enter the deterministic
guardrail callback; the tool result returns through the assistant context aggregator
before the next answer. Conversation context retains returned booking IDs so a caller
can say “cancel that appointment.” Each call has an isolated in-memory booking store.
These are demo mutations, not appointments in an external clinic system.

## Reliability contract

- 16 kHz, mono, 16-bit PCM WAV; 0.1–30 seconds per recording.
- 60-second pipeline deadline; one turn per call; two concurrent turns per process.
- Maximum 24 sessions, 12 turns per session, 30-minute idle expiry.
- Turn IDs are idempotent within the session. Reusing an ID with different audio is rejected.
- Automatic retries never repeat booking tools. A failed speech response can follow a
  successful booking mutation; inspect the returned booking list before trying again.
- End call removes the session. Abandoned sessions expire and are pruned when new calls
  are created. Only the latest reply audio is cached; raw input files are deleted after each turn.
- Calls are excluded from shared benchmark history. Provider logs may still contain
  conversational data; use fictional details. No production identity or authorization model is provided.
- The combined Render launcher waits for API health, then exposes Streamlit. It exits
  if either process fails. Free-instance sleep and restart discard all in-memory state.

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
use **Live call → Test recording**, upload a 16 kHz WAV, and inspect booking activity.
For a human microphone acceptance test, speak the same requests and confirm playback.
Synthetic-audio tests do not establish real microphone quality or a reliability percentage.

Measure TTFA separately from full turn duration. TTFA starts at the backend speech-end
marker and ends at first generated audio; upload and browser playback add latency.
The current implementation returns the completed audio file, not a streaming playback buffer.

## Release checks

1. Run unit tests and opt-in live evaluation.
2. Inspect the staged diff for secrets; `.env` and `.venv` stay ignored.
3. Push `codex/render-deploy`, then deploy that commit in Render (free plan).
4. Confirm health, microphone controls, reference tabs, a completed voice turn, and booking state.
5. Record any untested browser/device behavior explicitly.
