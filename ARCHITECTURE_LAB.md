# VoiceOps — hear the architecture

VoiceOps compares orchestration choices with identical WAV inputs, live Groq and Edge-TTS,
measured events, supplied correctness criteria and exportable reports. The booking call studio
is one optional example at `/studio/`. This document supersedes the original PRD surface.

## Controlled comparisons

| Mode | LLM text before synthesis | Audio delivery | Deterministic policy |
| --- | --- | --- | --- |
| Buffered | Hold full text | Hold full audio | No |
| Full text · streamed audio | Hold full text | Progressive PCM | No |
| Streamed text · held audio | Incremental | Hold full audio | No |
| Streaming | Incremental | Progressive PCM | No |
| Guarded streaming | Incremental | Progressive PCM | Yes |

Compare buffered vs full-text/streamed-audio to vary delivery only; buffered vs streamed-text/held-audio
varies text gating only. Streaming vs guarded varies deterministic checks. Every mode shares recorded-turn
Groq Whisper, the same LLM, prompt, reference material and tools. There are no injected delays.
Native speech-to-speech, continuous transcription and full-duplex interruptions are not implemented.

## Experiment and statistical contract

Choose 1–30 repetitions per mode. The browser records a randomized starting offset, then rotates order
each repetition. Optional trial-zero warm-ups remain visible and consume quota but are excluded from
measured summaries. Each trial starts fresh context. Process uptime is recorded; provider cache state
remains uncontrolled. First measured trials are retained rather than silently discarded.

Median uses completed measured runs with finite browser playback metrics. Failures and counts remain
visible. Nearest-rank p95 is withheld below 20 samples and remains exploratory above that threshold.
Paired effects match input SHA-256 and repetition. Percentile bootstrap intervals use 1,000 resamples
and require at least five pairs. They describe repeated trials on this input, not a population of speakers
or tasks. Network variation, provider load and caching remain uncontrolled; no universal speedup is claimed.

Tasks support required/forbidden facts (normalized literal matching), exact JSON field values, optional
substring matching and action/amount/outcome checks that must match the same tool call. These checks test
supplied criteria, not semantic truth. Each response shows pass/fail/unscored alongside latency. An
unguarded baseline can deliberately fail a policy criterion while completing its speech pipeline.
All actions are simulations without external effects. Every mode enforces transport validation;
guarded mode additionally checks the action allowlist and amount cap.

## Measurement boundaries

Primary browser latency starts at the trial-ready signal and ends at first scheduled AudioContext PCM.
It includes server work and response delivery. Initial WAV upload, speech duration, pause detection and
physical device latency are excluded. Upload/admission round trip is recorded once per experiment.
Microphone inputs record last-above-threshold capture block to detected endpoint; this is an estimate,
not an acoustic measurement, and deliberate user wait before running is excluded.

Reports separately record first PCM receipt, scheduling lead, late packet count and scheduled silence
gaps. These are not hardware underrun measurements. Browser baseLatency/outputLatency are labelled
estimates when available. No mouth-to-ear total is claimed. Server event times use a separate monotonic
clock starting before pipeline construction. STT request to transcript, transcript to first LLM text,
and first synthesis request to first PCM are observed spans. Stages may overlap and must not be summed.
Tool overhead measures local policy evaluation, not the full LLM/tool round trip.

## Reproducibility and recovery

JSON includes spec, input hash, results, observed events, deployment commit when RENDER_GIT_COMMIT is
available, Python/library versions, voice, sample rate, region when known, and LLM settings (temperature
0; max_completion_tokens 1024, including reasoning tokens). Provider output is not guaranteed identical.
CSV contains one row per trial. Reports retain partial, failed and interrupted evidence.

History stays in tab memory by default. Explicit opt-in saves reports to localStorage for recovery after
reload. Transcripts and settings are included; recordings and blob URLs are excluded. Clear removes saved
and in-memory reports. Nothing is published to a shared archive. Switching task types preserves selected
audio, reference material and criteria; Use sample voice explicitly replaces them with a chosen fixture.
The older studio benchmark menu was retired because its scenario labels did not select distinct fixtures.

## Runtime and usage limits

The public gateway serves the light lab, same-origin WebSocket experiments and proxied Streamlit studio.
The private API stays on loopback. API and gateway share a Python process/provider imports on free Render.
Each pipeline has a 60-second deadline. Two experiments can run concurrently. Disconnect cancels active
work. Browser recordings cap at 25 seconds; API WAV validation permits up to 30 seconds.

SQLite reservations are atomic and shared across lab and studio. Defaults: 300 attempted trials per
server/UTC day, 150/address/day, 12 experiment starts/address/10-minute window. Studio shares one client
bucket. Reservations include planned warm-ups, failures and cancellations; they are not refunded.
Set VOICEOPS_DAILY_TRIALS, VOICEOPS_CLIENT_DAILY_TRIALS, VOICEOPS_STARTS_PER_10_MIN and
VOICEOPS_BUDGET_PATH in the server environment. Ephemeral redeploys may reset counters. This is a usage
brake, not authentication or a guaranteed monetary cap. Free-host sleep can delay availability.

## Run and verify

```bash
pip install '.[dev]'
python scripts/start_render.py
pytest -q
node --test tests/*.test.mjs
python scripts/evaluate_architectures.py --url ws://localhost:10000/lab/ws --modes buffered text_buffered audio_buffered streaming guarded
python scripts/evaluate_architectures.py --url ws://localhost:10000/lab/ws --task extraction
python scripts/evaluate_architectures.py --url ws://localhost:10000/lab/ws --task action
```

Configure GROQ_API_KEY in ignored .env; optional GROQ_WHISPER_MODEL, GROQ_LLM_MODEL and EDGE_TTS_VOICE.
Open port 10000 (or PORT). CLI reports contain server measurements only; use the browser for playback
acceptance tests. Live tests consume quota. The public repo includes controlled-provider lifecycle,
evaluation, atomic budget, statistics, scheduling-gap and recovery-serialization tests.
