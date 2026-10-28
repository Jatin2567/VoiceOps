"""Deterministic policy checks shared by Pipecat frames and Groq tool callbacks."""
import asyncio
import json
import time

from pipecat.frames.frames import (
    Frame, FunctionCallInProgressFrame, FunctionCallResultFrame, OutputAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from backend.domain.models.guardrail import GuardrailAction, GuardrailEvaluationRequest
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService


class DeterministicSidecarInterceptor(FrameProcessor):
    def __init__(self, trace_id: str, guardrail_service: IGuardrailPolicyService,
                 callback_driven: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._trace_id = trace_id
        self._guardrail_service = guardrail_service
        self._callback_driven = callback_driven
        self._interception_count = 0
        self._violations_detected = []
        self._total_overhead_ms = 0.0
        self._is_audio_paused = False
        self._held_audio_frames = []
        self._evaluation_lock = asyncio.Lock()

    @property
    def interception_count(self):
        return self._interception_count

    @property
    def violations_detected(self):
        return list(self._violations_detected)

    @property
    def total_overhead_ms(self):
        return self._total_overhead_ms

    async def _evaluate(self, function_name, arguments):
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        start = time.perf_counter()
        result = await self._guardrail_service.evaluate_tool_call(GuardrailEvaluationRequest(
            trace_id=self._trace_id, function_name=function_name, arguments=dict(arguments)))
        self._total_overhead_ms += (time.perf_counter() - start) * 1000
        self._interception_count += 1
        self._violations_detected.extend(
            f"[{v.policy_type.value}] {v.message}" for v in result.violations)
        if result.action == GuardrailAction.BLOCK:
            self._held_audio_frames.clear()
            return {"status": "error", "error_code": "POLICY_VIOLATION",
                    "message": result.feedback_to_agent}
        return {"status": "modified" if result.action == GuardrailAction.MODIFY else "success",
                "message": result.feedback_to_agent, "data": result.arguments}

    async def handle_tool_call(self, params):
        """Deliver the validated result through Groq's registered callback protocol."""
        async with self._evaluation_lock:
            self._is_audio_paused = True
            try:
                payload = await self._evaluate(params.function_name, params.arguments)
                await params.result_callback(payload)
            except BaseException:
                self._held_audio_frames.clear()
                raise
            finally:
                self._is_audio_paused = False
            held, self._held_audio_frames = self._held_audio_frames, []
            for frame, direction in held:
                await self.push_frame(frame, direction)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Start and cancel frames must initialize/stop the base processor queues.
        await super().process_frame(frame, direction)
        if isinstance(frame, FunctionCallInProgressFrame) and not self._callback_driven:
            payload = await self._evaluate(frame.function_name, frame.arguments)
            await self.push_frame(FunctionCallResultFrame(
                function_name=frame.function_name, tool_call_id=frame.tool_call_id,
                arguments=frame.arguments, result=payload), direction)
            return
        if self._is_audio_paused and isinstance(frame, OutputAudioRawFrame):
            self._held_audio_frames.append((frame, direction))
            return
        await self.push_frame(frame, direction)
