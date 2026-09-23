"""Driving adapter: WebSocket route for Phase 2 continuous streaming."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter(prefix="/ws", tags=["Streaming WebSockets"])


@router.websocket("/v1/stream/{session_id}")
async def websocket_streaming_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for Phase 2 continuous bidirectional audio streaming.
    Phase 1 establishes the connection protocol and handles ping/pong verification.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for session: {session_id}")

    try:
        # Send initial handshake acknowledgement
        await websocket.send_json({
            "event": "connected",
            "session_id": session_id,
            "message": "VoiceOps continuous streaming channel ready.",
            "protocol_version": "v1",
        })

        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                # Echo test audio chunk or handle incoming PCM bytes in Phase 2
                await websocket.send_json({
                    "event": "chunk_received",
                    "byte_length": len(message["bytes"]),
                })
            elif "text" in message and message["text"]:
                await websocket.send_json({
                    "event": "text_ack",
                    "received": message["text"],
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
