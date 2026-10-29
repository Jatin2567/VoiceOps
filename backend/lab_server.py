"""Public architecture lab and a same-origin gateway to the existing call studio.

The legacy API remains on loopback. Only the bounded experiment channel and
the Streamlit studio are exposed by this process.
"""
import asyncio
import base64
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend.domain.models.experiment import ExperimentSpec
from backend.application.services.architecture_lab import run_architecture
from backend.application.services.voice_calls import CallError, VoiceCalls

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
active = 0
STUDIO = os.getenv("STUDIO_ORIGIN", "http://127.0.0.1:8501")


@asynccontextmanager
async def lifespan(app):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None)) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
@app.get("/_stcore/health")
async def health():
    return {"status": "healthy", "service": "VoiceOps architecture lab"}


@app.websocket("/lab/ws")
async def experiment(ws: WebSocket):
    global active
    # Same-origin browsers only; no credential-bearing or third-party embed API.
    origin = ws.headers.get("origin", "")
    if origin and urlsplit(origin).netloc != ws.headers.get("host"):
        await ws.close(code=1008)
        return
    await ws.accept()
    if active >= 2:
        await ws.send_json({"type": "error", "message": "Two experiments are already running. Try again shortly."})
        await ws.close()
        return
    active += 1
    sender = work = None
    try:
        data = await asyncio.wait_for(ws.receive_json(), 20)
        spec = ExperimentSpec.model_validate(data.get("spec", {}))
        encoded = data.get("audio", "")
        if not isinstance(encoded, str) or len(encoded) > 1280060:
            raise ValueError("Use a recording under 25 seconds.")
        audio = base64.b64decode(encoded, validate=True)
        VoiceCalls.validate_audio(audio)
        for trial, mode in spec.schedule():
            await ws.send_json({"type": "run_start", "trial": trial, "mode": mode})
            ready = await asyncio.wait_for(ws.receive_json(), 20)
            if ready.get("type") != "ready":
                raise ValueError("Expected a trial-ready signal.")
            queue = asyncio.Queue(maxsize=2400)

            async def send_packets():
                while True:
                    packet = await queue.get()
                    try:
                        await ws.send_json(packet)
                    finally:
                        queue.task_done()

            sender = asyncio.create_task(send_packets())
            work = asyncio.create_task(run_architecture(spec, mode, audio, queue.put_nowait))
            done, _ = await asyncio.wait([sender, work], return_when=asyncio.FIRST_COMPLETED)
            if sender in done:
                await sender  # Disconnect cancels provider work in finally.
            result = await work
            await asyncio.wait_for(queue.join(), 15)
            sender.cancel()
            with suppress(asyncio.CancelledError):
                await sender
            sender = None
            await ws.send_json({"type": "result", "trial": trial, **result})
            # Browser finishes scheduled playback before the next architecture starts.
            ack = await asyncio.wait_for(ws.receive_json(), 90)
            if ack.get("type") != "next":
                raise ValueError("Unexpected experiment acknowledgement.")
        await ws.send_json({"type": "complete"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    except (ValueError, ValidationError, CallError, asyncio.TimeoutError):
        with suppress(Exception):
            await ws.send_json({"type": "error", "message": "Experiment could not finish. Check the recording and configuration, or retry after the service recovers."})
    finally:
        for future in (sender, work):
            if future and not future.done():
                future.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await future
        active -= 1
        with suppress(Exception):
            await ws.close()


@app.api_route("/studio/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def studio(request: Request, path: str):
    target = STUDIO + request.url.path
    if request.url.query:
        target += "?" + request.url.query
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("connection", "transfer-encoding", "content-length")}
    try:
        response = await request.app.state.client.request(request.method, target, headers=headers,
            data=await request.body(), allow_redirects=False)
    except aiohttp.ClientError:
        return Response("Call studio is starting. Please refresh shortly.", status_code=503)
    async def body():
        try:
            async for chunk in response.content.iter_chunked(65536):
                yield chunk
        finally:
            response.release()
    # aiohttp decodes compressed upstream bodies.
    outgoing = {k: v for k, v in response.headers.items() if k.lower() not in
                ("content-encoding", "content-length", "transfer-encoding", "connection")}
    return StreamingResponse(body(), status_code=response.status, headers=outgoing)


@app.websocket("/studio/{path:path}")
async def studio_socket(ws: WebSocket, path: str):
    target = STUDIO + ws.url.path
    if ws.url.query:
        target += "?" + ws.url.query
    protocols = [s.strip() for s in ws.headers.get("sec-websocket-protocol", "").split(",") if s.strip()]
    headers = {k: v for k, v in ws.headers.items() if k.lower() in ("origin", "cookie", "host")}
    async with ws.app.state.client.ws_connect(target, headers=headers, protocols=protocols, max_msg_size=8*1024*1024) as upstream:
        await ws.accept(subprotocol=upstream.protocol)
        async def inward():
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if message.get("bytes") is not None:
                    await upstream.send_bytes(message["bytes"])
                elif message.get("text") is not None:
                    await upstream.send_str(message["text"])
        async def outward():
            async for message in upstream:
                if message.type == aiohttp.WSMsgType.TEXT:
                    await ws.send_text(message.data)
                elif message.type == aiohttp.WSMsgType.BINARY:
                    await ws.send_bytes(message.data)
        futures = [asyncio.create_task(inward()), asyncio.create_task(outward())]
        try:
            await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for future in futures:
                future.cancel()
            await asyncio.gather(*futures, return_exceptions=True)


app.mount("/shared", StaticFiles(directory=ROOT / "frontend" / "components" / "conversation"), name="shared")
app.mount("/", StaticFiles(directory=ROOT / "frontend" / "lab", html=True), name="lab")
