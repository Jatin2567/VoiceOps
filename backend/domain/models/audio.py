"""Domain models for audio formats and stream chunks."""
from typing import Optional
from pydantic import BaseModel, Field


class AudioFormat(BaseModel):
    """Standardized audio specifications across all topologies."""
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz (16kHz)")
    num_channels: int = Field(default=1, description="Number of audio channels (1=Mono)")
    sample_width: int = Field(default=2, description="Bytes per sample (2 = 16-bit PCM)")
    encoding: str = Field(default="linear16", description="PCM encoding type")


class AudioChunk(BaseModel):
    """Discrete chunk of raw audio payload."""
    sequence_id: int = Field(..., description="Monotonically increasing sequence index")
    data: bytes = Field(..., description="Raw PCM audio bytes")
    duration_ms: float = Field(..., description="Duration of this chunk in milliseconds")
    is_final: bool = Field(default=False, description="Flag indicating end of audio stream")


class AudioBenchmarkFile(BaseModel):
    """Metadata describing a test benchmark .wav asset."""
    file_path: str = Field(..., description="Absolute or relative file path to the audio file")
    file_name: str = Field(..., description="Base filename")
    duration_seconds: float = Field(..., description="Total duration of audio in seconds")
    sample_rate: int = Field(default=16000, description="Sample rate in Hz")
    description: Optional[str] = Field(default=None, description="Test utterance description")
