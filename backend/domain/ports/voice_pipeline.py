"""Domain port defining the Voice Pipeline contract."""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from backend.domain.models.benchmark import BenchmarkRequest, BenchmarkResult


class IVoicePipeline(ABC):
    """Abstract port for executing a voice audio pipeline DAG."""

    @abstractmethod
    async def run_benchmark(self, request: BenchmarkRequest) -> BenchmarkResult:
        """
        Execute a voice turn benchmark against the audio input specified in request.
        Operates non-invasively, returning the calculated latency and transcription metrics.
        """
        raise NotImplementedError

    @abstractmethod
    async def stream_audio(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        trace_id: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Process a live bidirectional audio stream.
        Receives input PCM audio chunks and yields synthesized output PCM audio chunks.
        """
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully terminate any active pipeline runners and release resources."""
        raise NotImplementedError
