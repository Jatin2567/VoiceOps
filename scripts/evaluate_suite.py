"""Versioned, varied-input evaluation. Keeps partial evidence on failure/cancel."""
import argparse
import asyncio
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import websockets


async def run(args):
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "frontend/lab/suite-v1.json").read_text(encoding="utf-8"))
    report = {"suite_id": manifest["id"], "manifest": manifest, "modes": args.modes,
              "created_at": datetime.now(timezone.utc).isoformat(), "status": "running", "runs": [],
              "measurement": "Server-only observed clocks; no browser playback or acoustic measurement"}
    def save():
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    try:
        selected = manifest["cases"] if not args.cases else [c for c in manifest["cases"] if c["id"] in args.cases]
        if not selected or (args.cases and len(selected) != len(set(args.cases))):
            raise ValueError("Unknown suite case")
        report["selected_cases"] = [c["id"] for c in selected]
        for index, case in enumerate(selected):
            audio = (root / "frontend/lab" / case["audio"].lstrip("/")).read_bytes()
            expected_hash = hashlib.sha256(audio).hexdigest()
            spec = {"modes": args.modes, "repeats": args.repeats, "order_offset": index % len(args.modes), **case["spec"]}
            async with websockets.connect(args.url, max_size=2000000, open_timeout=30) as ws:
                await ws.send(json.dumps({"spec": spec, "audio": base64.b64encode(audio).decode()}))
                complete = False
                async for raw in ws:
                    message = json.loads(raw)
                    if message["type"] == "run_start":
                        await ws.send(json.dumps({"type": "ready"}))
                    elif message["type"] == "result":
                        if message["audio_sha256"] != expected_hash:
                            raise RuntimeError("Input hash mismatch")
                        report["runs"].append({**message, "case_id": case["id"], "task": case["spec"]["task"]})
                        print(case["id"], message["mode"], message["status"], message["evaluation"]["status"], flush=True)
                        save()
                        await ws.send(json.dumps({"type": "next"}))
                    elif message["type"] == "error":
                        raise RuntimeError(message["message"])
                    elif message["type"] == "complete":
                        complete = True
                        break
                if not complete:
                    raise RuntimeError("Experiment channel closed before completion")
        report["status"] = "completed"
    except BaseException as exc:
        report["status"] = "interrupted"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        save()
    if any(r["status"] != "completed" for r in report["runs"]):
        raise RuntimeError("Suite contains failed trials; inspect the report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8511/lab/ws")
    parser.add_argument("--modes", nargs="+", choices=["buffered", "text_buffered", "audio_buffered", "streaming", "guarded"], default=["buffered", "streaming", "guarded"])
    parser.add_argument("--repeats", type=int, choices=range(1, 31), default=1)
    parser.add_argument("--output", default=".venv/suite-v1-report.json")
    parser.add_argument("--cases", nargs="+", help="Optional explicit case IDs for a partial acceptance run")
    asyncio.run(run(parser.parse_args()))
