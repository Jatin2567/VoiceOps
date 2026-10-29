"""Opt-in live experiment replay; reports server metrics, never browser playback."""
import argparse
import asyncio
import base64
import json
from pathlib import Path
import websockets


async def main(args):
    spec = {"modes": ["buffered", "streaming", "guarded"], "repeats": args.repeats,
            "task": args.task, "instruction": "Reply in two short sentences.",
            "action_limit": 100, "allowed_actions": ["refund", "credit", "reserve"]}
    runs = []
    async with websockets.connect(args.url, max_size=2000000, open_timeout=30) as ws:
        await ws.send(json.dumps({"spec": spec, "audio": base64.b64encode(Path(args.audio).read_bytes()).decode()}))
        async for raw in ws:
            message = json.loads(raw)
            if message["type"] == "run_start":
                await ws.send(json.dumps({"type": "ready"}))
            elif message["type"] == "result":
                runs.append(message)
                print(message["mode"], message["status"], message["metrics"], "tools", message["tools"], flush=True)
                await ws.send(json.dumps({"type": "next"}))
            elif message["type"] == "error":
                raise RuntimeError(message["message"])
            elif message["type"] == "complete":
                break
    report = {"spec": spec, "input": args.audio, "measurement": "Server only; no browser playback or acoustic latency", "runs": runs}
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert len(runs) == 3 * args.repeats and all(r["status"] == "completed" for r in runs)
    assert len({r["audio_sha256"] for r in runs}) == 1
    if args.task == "action":
        assert all(r["tools"] for r in runs), "Model did not execute every expected tool call."
        assert all(t["status"] == "blocked" for r in runs if r["mode"] == "guarded" for t in r["tools"])
    print("Completed with identical input hashes. Inspect responses for correctness.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8505/lab/ws")
    parser.add_argument("--audio", default="frontend/lab/sample.wav")
    parser.add_argument("--task", choices=["conversation", "action"], default="conversation")
    parser.add_argument("--repeats", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--output", default=".venv/architecture-evaluation.json")
    asyncio.run(main(parser.parse_args()))
