"""Custom Edge-TTS adapter integrating Microsoft Edge-TTS with Pipecat DAG pipelines."""
import asyncio
import os
from typing import AsyncGenerator, Optional

from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService


class EdgeTTSService(TTSService):
    """
    Custom Pipecat TTSService adapter wrapping Microsoft edge-tts.
    Fulfills PRD Directive 3 by executing a background ffmpeg decoding subprocess,
    intercepting audio bytes, and yielding raw PCM audio frames downstream.
    """

    DEFAULT_VOICE = "en-US-ChristopherNeural"
    DEFAULT_SAMPLE_RATE = 16000
    PCM_CHUNK_SIZE = 3200  # 3200 bytes = 100ms of 16kHz 16-bit mono PCM

    def __init__(
        self,
        voice: Optional[str] = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        **kwargs
    ):
        from pipecat.services.tts_service import TTSSettings
        resolved_voice = voice or os.getenv("EDGE_TTS_VOICE", self.DEFAULT_VOICE)
        settings = kwargs.pop("settings", None) or TTSSettings(
            model=None,
            voice=resolved_voice,
            language="en",
        )
        super().__init__(sample_rate=sample_rate, settings=settings, **kwargs)
        self._voice = resolved_voice
        self._sample_rate = sample_rate
        self._ffmpeg_exe = self._resolve_ffmpeg()
        logger.info(
            f"EdgeTTSService initialized with voice={self._voice}, "
            f"sample_rate={self._sample_rate}, ffmpeg={self._ffmpeg_exe}"
        )

    def _resolve_ffmpeg(self) -> str:
        """Locate ffmpeg executable from imageio_ffmpeg or system PATH."""
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return "ffmpeg"

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        """
        Run text-to-speech synthesis using edge-tts and stream PCM frames.

        Args:
            text: Text string to synthesize into speech.
            context_id: Pipecat context identifier for the audio turn.

        Yields:
            TTSStartedFrame, TTSAudioRawFrame (which is an AudioRawFrame), TTSStoppedFrame.
        """
        if not text or not text.strip():
            logger.debug("EdgeTTSService received empty text; skipping synthesis.")
            yield TTSStartedFrame(context_id=context_id)
            yield TTSStoppedFrame(context_id=context_id)
            return

        yield TTSStartedFrame(context_id=context_id)
        await self.start_tts_usage_metrics(text)

        proc = None
        feeder_task = None

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text.strip(), self._voice)

            # Spawn ffmpeg subprocess to decode edge-tts MP3 stream directly to raw s16le PCM
            proc = await asyncio.create_subprocess_exec(
                self._ffmpeg_exe,
                "-hide_banner",
                "-loglevel", "error",
                "-i", "pipe:0",
                "-f", "s16le",
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", str(self._sample_rate),
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def feed_edge_tts_to_ffmpeg():
                try:
                    async for chunk in communicate.stream():
                        if chunk.get("type") == "audio" and proc.stdin:
                            proc.stdin.write(chunk["data"])
                            await proc.stdin.drain()
                except Exception as e:
                    logger.error(f"Error in edge-tts audio feed: {e}")
                finally:
                    if proc.stdin and not proc.stdin.is_closing():
                        try:
                            proc.stdin.close()
                            await proc.stdin.wait_closed()
                        except Exception:
                            pass

            feeder_task = asyncio.create_task(feed_edge_tts_to_ffmpeg())

            # Read PCM frames from ffmpeg stdout and yield downstream
            has_yielded_audio = False
            while True:
                pcm_data = await proc.stdout.read(self.PCM_CHUNK_SIZE)
                if not pcm_data:
                    break
                has_yielded_audio = True
                # TTSAudioRawFrame is a subclass of AudioRawFrame with context_id
                yield TTSAudioRawFrame(
                    audio=pcm_data,
                    sample_rate=self._sample_rate,
                    num_channels=1,
                    context_id=context_id,
                )

            await feeder_task
            await proc.wait()

            if not has_yielded_audio or proc.returncode:
                raise RuntimeError("Speech synthesis returned no usable audio.")

        except Exception as e:
            yield ErrorFrame(error=f"Edge-TTS synthesis error: {e}")
        finally:
            if feeder_task and not feeder_task.done():
                feeder_task.cancel()
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            yield TTSStoppedFrame(context_id=context_id)
