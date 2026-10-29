"""Internal API for isolated push-to-talk browser sessions."""
import base64
import binascii
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.application.services.voice_calls import voice_calls, CallError

router = APIRouter(prefix="/calls", tags=["Microphone calls"])


class VoiceTurn(BaseModel):
    turn_id: UUID
    audio_base64: str = Field(max_length=1280060)


@router.post("")
async def create_call():
    try:
        return {"session_id": voice_calls.create(), "expires_in_seconds": voice_calls.TTL}
    except CallError as exc:
        raise HTTPException(exc.status, exc.message)
    except ValueError:
        raise HTTPException(503, "Groq is not configured on this server.")


@router.post("/{session_id}/turns")
async def voice_turn(session_id: UUID, payload: VoiceTurn):
    try:
        audio = base64.b64decode(payload.audio_base64, validate=True)
        return await voice_calls.turn(str(session_id), str(payload.turn_id), audio)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Invalid audio encoding.")
    except CallError as exc:
        raise HTTPException(exc.status, exc.message)


@router.delete("/{session_id}")
async def end_call(session_id: UUID):
    try:
        voice_calls.end(str(session_id))
        return {"status": "ended"}
    except CallError as exc:
        raise HTTPException(exc.status, exc.message)
