"""Create the fictional, general-purpose voice input shipped with the lab."""
import asyncio
import subprocess
from pathlib import Path
import edge_tts
import imageio_ffmpeg


async def main():
    target = Path("frontend/lab")
    intermediate = Path(".venv/lab-sample.mp3")
    samples = {"sample": "Explain how a rainbow forms in three short sentences.",
               "knowledge": "How long do I have to return an unused item, and do I need a receipt?",
               "extraction": "My name is Alex Test. I need two blue notebooks delivered on Friday.",
               "action": "Simulate a refund of one hundred and fifty units."}
    for name, text in samples.items():
        await edge_tts.Communicate(text, "en-US-JennyNeural").save(str(intermediate))
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(intermediate),
                        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(target / (name + ".wav"))], check=True)
        intermediate.unlink()


if __name__ == "__main__":
    asyncio.run(main())
