"""Submit a completed browser utterance without replaying its duration on the server."""
from dataclasses import dataclass
from pipecat.frames.frames import DataFrame
from pipecat.services.groq.stt import GroqSTTService


@dataclass
class RecordedUtteranceFrame(DataFrame):
    audio: bytes


class RecordedGroqSTTService(GroqSTTService):
    async def process_frame(self, frame, direction):
        if isinstance(frame, RecordedUtteranceFrame):
            # run_stt accepts a WAV container and emits the same transcription
            # frames as the normal Pipecat segmented audio path.
            await self.process_generator(self.run_stt(frame.audio))
        else:
            await super().process_frame(frame, direction)
