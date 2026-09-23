"""VAD Processor initialization and configuration using Silero VAD."""
from typing import Optional

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.processors.audio.vad_processor import VADProcessor


def create_vad_processor(
    confidence: float = 0.7,
    start_secs: float = 0.2,
    stop_secs: float = 0.5,
    sample_rate: int = 16000,
) -> VADProcessor:
    """
    Factory creating a configured Silero VAD processor for voice activity detection,
    producing UserStartedSpeakingFrame and UserStoppedSpeakingFrame.
    """
    params = VADParams(
        confidence=confidence,
        start_secs=start_secs,
        stop_secs=stop_secs,
    )
    vad_analyzer = SileroVADAnalyzer(sample_rate=sample_rate, params=params)
    processor = VADProcessor(vad_analyzer=vad_analyzer)
    logger.debug(f"Silero VAD processor created (confidence={confidence}, stop_secs={stop_secs}s).")
    return processor
