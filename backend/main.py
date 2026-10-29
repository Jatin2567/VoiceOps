"""VoiceOps Enterprise: FastAPI ASGI Application Factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.dependencies import get_container
from backend.api.v1.routes_benchmark import router as benchmark_router
from backend.api.v1.routes_telemetry import router as telemetry_router
from backend.api.v1.ws_streaming import router as ws_router
from backend.api.v1.routes_calls import router as calls_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Starts background Outbox telemetry flush worker on startup,
    and gracefully flushes residual queues on shutdown.
    """
    logger.info("Starting VoiceOps Enterprise FastAPI Application...")
    container = get_container()

    # Start the background Outbox worker
    await container.flush_worker.start()
    logger.info("TelemetryFlushWorker background task started.")

    yield

    logger.info("Shutting down VoiceOps Enterprise Application...")
    await container.benchmark_runner.stop()
    await container.flush_worker.stop()
    logger.info("TelemetryFlushWorker stopped cleanly.")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title="VoiceOps Enterprise API",
        description="Zero-Cost Voice AI Benchmarking, Latency Observability & Deterministic Guardrails Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS) for Streamlit frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "status": "healthy",
            "service": "VoiceOps Backend",
            "version": "0.1.0",
        }

    # Mount API v1 Routers
    app.include_router(benchmark_router, prefix="/v1")
    app.include_router(telemetry_router, prefix="/v1")
    app.include_router(calls_router, prefix="/v1")
    app.include_router(ws_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
