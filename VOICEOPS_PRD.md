# Product Requirements Document: VoiceOps Enterprise

> Current architecture showcase: see [ARCHITECTURE_LAB.md](ARCHITECTURE_LAB.md) for the implemented
> three-mode lab and measurement contract. The original design below is retained as project history.

## 1. System Overview
VoiceOps is a modular Voice AI benchmarking and observability platform designed to quantify Time-to-First-Audio (TTFA) latency and validate deterministic policy guardrails across two architectural modes: Cascade and Hybrid.

**Tech Stack:**
*   **Frontend:** Streamlit (deployed via Streamlit Community Cloud)
*   **Backend:** FastAPI (deployed via Render Web Services)
*   **Audio Pipeline Framework:** `pipecat-ai` (Frame-Processor DAG architecture)
*   **State & Queuing:** Upstash Redis (Outbox pattern)
*   **Persistence:** Supabase PostgreSQL (SQLAlchemy)
*   **Models:** Groq API (Whisper STT, Groq LLM LLM), Microsoft `edge-tts` (TTS).

## 2. Directory Structure (Hexagonal Architecture)
The codebase MUST strictly adhere to the following Ports & Adapters structure to ensure vendor interchangeability and separation of concerns.

```text
/voiceops
├── pyproject.toml                      
├── docker-compose.yml                  
├── /frontend                           
│   ├── app.py                          
│   ├── /components                     
│   └── /assets                         # Mock .wav test files
└── /backend
    ├── main.py                         # ASGI Application Factory
    ├── /api                            # Driving Adapters (FastAPI Routers)
    │   └── /v1
    │       ├── routes_benchmark.py     
    │       ├── ws_streaming.py         
    │       └── routes_telemetry.py     
    ├── /domain                         # Pure Python Entities & Interfaces
    │   ├── /models                     
    │   └── /ports                      # IBookingRepository, ITelemetryRepository, IVoicePipeline
    ├── /application                    # Orchestration Services
    │   ├── /services                   # benchmark_runner.py, guardrail_service.py
    │   └── /telemetry                  # worker.py (Async flush to Supabase)
    ├── /infrastructure                 # Driven Adapters
    │   ├── /persistence                # supabase_client.py, mock_booking_repo.py
    │   ├── /queue                      # upstash_client.py
    │   └── /providers                  # groq_client.py, edge_tts_client.py
    └── /pipelines                      # Pipecat Audio DAGs
        ├── factory.py                  
        ├── /processors                 # telemetry_processor.py, vad_processor.py, interceptor.py
        └── /modes                      # cascade_topology.py, hybrid_topology.py

3. Strict Architectural DirectivesWARNING: Failure to follow these directives will result in system crashes under load or corrupted TTFA metrics.Directive 1: Unified Pipecat Frame ProcessingDo NOT implement Phase 1 (discrete files) as standard HTTP synchronous functions.Both modes (Cascade, Hybrid) MUST be implemented as pipecat-ai pipelines using AudioRawFrame, TextFrame, and EndFrame.Phase 1 testing streams a static .wav file into the Pipecat pipeline. This ensures Phase 2 (WebSocket streaming) requires zero rewrites to the core logic.Directive 2: The FastAPI ASGI Concurrency TrapPipecat's PipelineRunner.run() is a blocking event loop.In /application/services/benchmark_runner.py, you MUST spawn the pipeline using asyncio.create_task().The FastAPI /benchmark endpoint must instantly return a 200 OK with a trace_id while the pipeline processes in the background. Streamlit will use this ID to poll /telemetry.Directive 3: Custom Edge-TTS AdapterPipecat does not have native Microsoft edge-tts support.In /infrastructure/providers/edge_tts_client.py, you MUST inherit from Pipecat's base TTSService.You must override run_tts() to execute the subprocess, intercept the audio bytes, and yield them downstream as Pipecat AudioRawFrame objects.Directive 4: Telemetry & The Outbox PatternMeasuring TTFA using time.time() inside standard routes is prohibited.TTFA must be captured non-invasively via a custom Pipecat Frame Processor (telemetry_processor.py) that observes UserStoppedSpeakingFrame ($T_0$) and AudioOutputFrame ($T_1$).The telemetry processor must LPUSH metrics to Upstash Redis. A background worker (/telemetry/worker.py) will flush metrics to Supabase to prevent DB I/O from adding latency to the voice stream.Directive 5: Deterministic Sidecar (Hybrid Mode)In Hybrid mode, the interceptor.py frame processor must intercept FunctionCallFrame events emitted by Groq.It must pause audio generation, call /application/services/guardrail_service.py to evaluate the policy against the mock_booking_repo, and inject the FunctionReturnFrame back into the pipeline before resuming.4. Agent Execution PlanAgent Instruction: Execute this plan strictly in sequence. Do NOT generate the next stage until the human user confirms the current stage is complete. Do not hallucinate external packages; rely on standard pipecat-ai, fastapi, pydantic, supabase, and redis SDKs.STAGE 1 - Initialization & Domain: Generate pyproject.toml, Docker Compose, and the entire /domain directory (Entities, Pydantic schemas, and Abstract Ports).STAGE 2 - Infrastructure: Generate /infrastructure. Build the mock_booking_repo and all provider adapters (groq_client, and specifically the custom edge_tts_client extending TTSService).STAGE 3 - The Pipecat Engine: Generate /pipelines and /application. Build the telemetry_processor, the interceptor, the two topological modes (Cascade, Hybrid), and the benchmark_runner.py using asyncio.create_task.STAGE 4 - The Surface Layers: Generate /api (FastAPI routes) and /frontend (Streamlit dashboard with polling metrics logic).
