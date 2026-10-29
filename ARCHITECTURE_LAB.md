# VoiceOps — hear the architecture

VoiceOps compares voice pipeline architectures using identical spoken inputs, live providers,
inspectable traces and downloadable evidence. General conversation, document questions,
extraction and simulated actions share one experiment harness. The earlier booking call studio
remains an optional example at `/studio/`. This document supersedes the original PRD's
two-mode benchmark surface; existing Pipecat and ports/adapters remain in use.

## Implemented comparisons

| Mode | Orchestration | Delivery |
| --- | --- | --- |
| Buffered cascade | Recorded-turn Whisper → Groq LLM → complete text → Edge-TTS | Hold all PCM until completion |
| Streaming cascade | Same STT and LLM → sentence-level Edge-TTS | Progressive PCM over WebSocket |
| Guarded streaming | Same streaming path with deterministic sandbox policy | Same progressive delivery |

These modes compare buffering, streaming and business-policy enforcement. Native speech-to-speech,
continuous transcription and full-duplex interruptions are not implemented. All three use Groq
Whisper on a completed utterance. There is no injected delay to manufacture a streaming advantage.

## Experiment contract

- Reuse exact WAV bytes and SHA-256 across every trial. Context starts fresh each trial.
- Use identical task settings, model configuration, tools and prompts across modes.
- Select up to three repetitions; run sequentially, rotating architecture order each repetition.
- Report observed events: STT request, transcript, first LLM text token, TTS request, first PCM,
  completion. Tool results include local evaluation duration, enforcement flag and outcome.
- Display completed counts, failures, median and nearest-rank p95. Never hide failed trials.
- Optional expected phrase checks only a substring; human review determines task quality.
- Every tool action is simulated. Guarded mode checks the allowlist and amount cap. All modes
  enforce basic type/range validation. Models can independently follow policy in baseline modes.
- Export configuration, provider models, input hash, responses, metrics and events as JSON;
  CSV contains one row per trial. History and recordings stay in browser memory, not a public archive.

## Measurement boundaries

Browser time starts with the trial-ready signal and ends at the first scheduled AudioContext PCM
sample. It includes server processing and delivery but excludes initial WAV upload, speech duration,
pause detection and physical device output latency. A short playback lead avoids immediate underruns.

Server time starts before pipeline construction, using a monotonic clock. STT latency starts at
the transcription submission marker. LLM first-token latency ends at first text (tool-only calls may
delay that marker). TTS first-audio latency spans first synthesis request to first PCM at output.
Stages can overlap, so these values are not an additive decomposition. Missing values remain null.

Provider responses can differ. Hosting warm-up, provider caching and network traffic are uncontrolled.
First trials are retained, not silently discarded. One to three samples support exploration, not
statistical superiority claims. Repeat and export across sessions for stronger evidence.

## Implementation and limits

The public gateway serves a static light interface and bounded same-origin WebSocket channel,
and proxies the Streamlit call studio. The legacy API stays on loopback. Render supervises the shared API/gateway process and the Streamlit process. Every mode executes a real Pipecat frame pipeline. Buffered gates text and audio;
streaming sends PCM as it crosses the output probe. No synthetic timings are presented as results.

Two experiments can run concurrently, each with at most nine trials and a 60-second deadline per
pipeline. Browser audio is capped at 25 seconds. Disconnects cancel provider work. Reports are
ephemeral and unauthenticated; use fictional inputs. Free-host sleeping affects availability.

## Reproduce

```bash
pip install '.[dev]'
python scripts/start_render.py
pytest -q
node --test tests/*.test.mjs
python scripts/evaluate_architectures.py --url ws://localhost:10000/lab/ws
python scripts/evaluate_architectures.py --url ws://localhost:10000/lab/ws --task action --audio frontend/lab/action.wav
```

Set `GROQ_API_KEY` in ignored `.env`. Optional settings: `GROQ_WHISPER_MODEL`, `GROQ_LLM_MODEL`,
`EDGE_TTS_VOICE`. Open port 10000 (or `PORT`) for the lab. CLI evaluation measures server stages;
browser playback must be tested separately. Live tests consume provider quota.

Core source: `backend/application/services/architecture_lab.py`, `backend/domain/models/experiment.py`,
`backend/lab_server.py`, and `frontend/lab/`. Controlled-provider lifecycle tests verify audio gating,
progressive delivery, observed stages, policy outcomes and bounded configuration.
