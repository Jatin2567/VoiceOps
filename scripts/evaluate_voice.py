"""Opt-in live-provider evaluation. Uses synthetic speech and isolated demo bookings."""
import argparse
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

import edge_tts
import httpx
import imageio_ffmpeg


async def recording(text, directory, name):
    mp3, wav = directory / f"{name}.mp3", directory / f"{name}.wav"
    await edge_tts.Communicate(text, "en-US-JennyNeural").save(str(mp3))
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-i", str(mp3), "-ar", "16000", "-ac", "1", str(wav)], check=True)
    return wav.read_bytes()


async def evaluate(base_url, output):
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "input": "synthetic spoken requests; live Groq and Edge-TTS", "cases": []}
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        async with httpx.AsyncClient(base_url=base_url, timeout=85) as client:
            created = await client.post("/v1/calls")
            created.raise_for_status()
            sid = created.json()["session_id"]
            slot = (datetime.now(timezone.utc) + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)
            phrase = slot.strftime("%B %d %Y at ten AM UTC")
            near = (datetime.now(timezone.utc) + timedelta(minutes=90)).strftime("%B %d %Y at %H:%M UTC")
            cases = [
                ("booking", f"Book a consultation for Alex Test on {phrase}. My phone number is nine eight seven six five four three two one zero."),
                ("conflict", f"Book another consultation for Sam Test at exactly the same time, {phrase}. The phone number is nine eight seven six five four three two one one. Do not move it to another time."),
                ("cancellation", "Cancel the confirmed appointment for Alex Test that you booked earlier."),
                ("unknown_cancellation", "Cancel booking ID nonexistent one two three. That is the exact ID."),
                ("near_booking", f"Book a consultation for Taylor Test on {near}. My phone number is nine eight seven six five four three two one two."),
                ("late_cancellation", "Cancel the appointment for Taylor Test that you just booked. Please use the cancellation tool to check the policy."),
            ]
            try:
                for name, text in cases:
                    audio = await recording(text, directory, name)
                    payload = {"turn_id": str(uuid4()), "audio_base64": base64.b64encode(audio).decode()}
                    response = await client.post(f"/v1/calls/{sid}/turns", json=payload)
                    response.raise_for_status()
                    result = response.json()
                    bookings = result["bookings"]
                    completed = result["status"] == "completed" and bool(result["audio_base64"])
                    expected = ((len(bookings) == 1 and bookings[0]["status"] == "confirmed")
                                if name in ("booking", "conflict") else
                                (len(bookings) == 1 and bookings[0]["status"] == "cancelled"))
                    passed = completed and expected
                    if name in ("near_booking", "late_cancellation"):
                        passed = completed and len(bookings) == 2 and bookings[1]["status"] == "confirmed"
                    if name in ("unknown_cancellation", "late_cancellation"):
                        passed = passed and bool(result["guardrail_violations"])
                    if name in ("booking", "cancellation"):
                        passed = passed and result["interception_count"] > 0
                    case = {"case": name, "passed": passed, "status": result["status"],
                            "trace_id": result["trace_id"], "tool_checks": result["interception_count"],
                            "policy_blocks": len(result["guardrail_violations"]),
                            "ttfa_ms": result["ttfa_ms"], "booking_count": len(bookings)}
                    report["cases"].append(case)
                    print(json.dumps(case), flush=True)
                    if name == "booking":
                        replay = await client.post(f"/v1/calls/{sid}/turns", json=payload)
                        replay.raise_for_status()
                        replayed = replay.json()
                        report["cases"].append({"case": "duplicate_turn", "passed": replayed["trace_id"] == result["trace_id"] and replayed["bookings"] == bookings})
            finally:
                await client.delete(f"/v1/calls/{sid}")
    report["passed"] = all(case["passed"] for case in report["cases"])
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="evaluation/live-results.json")
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(evaluate(args.base_url, args.output)) else 1)
