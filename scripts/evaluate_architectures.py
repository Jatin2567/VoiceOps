"""Opt-in live experiment replay; reports server metrics, never browser playback."""
import argparse
import asyncio
import base64
import json
from pathlib import Path
import websockets


async def main(args):
    spec = {"modes": args.modes, "repeats": args.repeats, "warmup": args.warmup,
            "task": args.task, "instruction": "Reply in two short sentences.",
            "action_limit": 100, "allowed_actions": ["refund", "credit", "reserve"]}
    contexts = {"knowledge": "Unused items may be returned within 30 days with the original receipt. Opened software cannot be returned.", "extraction": "Extract name, quantity, item, color and delivery_day."}
    criteria = {"conversation": {}, "knowledge": {"required_facts": ["30", "receipt"]}, "extraction": {"expected_fields": {"name": "Alex Test", "quantity": "2", "item": "notebooks", "color": "blue", "delivery_day": "Friday"}}, "action": {"expected_action": "refund", "expected_amount": 150, "expected_tool_status": "blocked"}}
    spec.update(context=contexts.get(args.task, ""), **criteria[args.task])
    if args.spec:
        spec.update(json.loads(Path(args.spec).read_text(encoding="utf-8")))
    args.audio = args.audio or ("frontend/lab/sample.wav" if args.task == "conversation" else f"frontend/lab/{args.task}.wav")
    runs = []
    async with websockets.connect(args.url, max_size=2000000, open_timeout=30) as ws:
        await ws.send(json.dumps({"spec": spec, "audio": base64.b64encode(Path(args.audio).read_bytes()).decode()}))
        async for raw in ws:
            message = json.loads(raw)
            if message["type"] == "run_start":
                await ws.send(json.dumps({"type": "ready"}))
            elif message["type"] == "result":
                runs.append(message)
                print(message["mode"], message["status"], message["metrics"], "evaluation", message.get("evaluation"), flush=True)
                await ws.send(json.dumps({"type": "next"}))
            elif message["type"] == "error":
                raise RuntimeError(message["message"])
            elif message["type"] == "complete":
                break
    report = {"spec": spec, "input": args.audio, "measurement": "Server only; no browser playback or acoustic latency", "runs": runs}
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert len(runs) == len(spec["modes"]) * (spec["repeats"] + int(spec["warmup"])) and all(r["status"] == "completed" for r in runs)
    assert len({r["audio_sha256"] for r in runs}) == 1
    if args.task == "action":
        assert all(r["tools"] for r in runs), "Model did not execute every expected tool call."
        assert all(t["status"] == "blocked" for r in runs if r["mode"] == "guarded" for t in r["tools"])
    print("Completed with identical input hashes. Inspect responses for correctness.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8505/lab/ws")
    parser.add_argument("--audio")
    parser.add_argument("--modes", nargs="+", choices=["buffered", "text_buffered", "audio_buffered", "streaming", "guarded"], default=["buffered", "streaming", "guarded"])
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument("--spec", help="JSON experiment configuration")
    parser.add_argument("--task", choices=["conversation", "knowledge", "extraction", "action"], default="conversation")
    parser.add_argument("--repeats", type=int, choices=range(1, 31), default=1)
    parser.add_argument("--output", default=".venv/architecture-evaluation.json")
    asyncio.run(main(parser.parse_args()))
