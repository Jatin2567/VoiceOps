"""Deterministic Sidecar Interceptor FrameProcessor for Hybrid mode (Directive 5)."""
import json
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    Frame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from backend.domain.models.guardrail import (
    GuardrailAction,
    GuardrailEvaluationRequest,
    GuardrailEvaluationResult,
)
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService


class DeterministicSidecarInterceptor(FrameProcessor):
    """
    Deterministic Sidecar FrameProcessor for Hybrid Mode.
    Fulfills PRD Directive 5:
    - Intercepts tool/function call events emitted by the LLM (Gemini Live).
    - Pauses downstream audio generation while validating policy.
    - Evaluates policy against the booking repository via IGuardrailPolicyService.
    - Injects the FunctionCallResultFrame back into the pipeline before resuming audio generation.
    """

    def __init__(
        self,
        trace_id: str,
        guardrail_service: IGuardrailPolicyService,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._trace_id = trace_id
        self._guardrail_service = guardrail_service

        self._interception_count: int = 0
        self._violations_detected: List[str] = []
        self._total_overhead_ms: float = 0.0
        self._is_audio_paused: bool = False
        self._held_audio_frames: List[Frame] = []

    @property
    def interception_count(self) -> int:
        return self._interception_count

    @property
    def violations_detected(self) -> List[str]:
        return list(self._violations_detected)

    @property
    def total_overhead_ms(self) -> float:
        return self._total_overhead_ms

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Intercept function call frames or gate audio frames during evaluation."""
        # 1. Detect function call event
        is_function_call = (
            isinstance(frame, FunctionCallInProgressFrame)
            or (hasattr(frame, "function_name") and hasattr(frame, "arguments"))
        )

        if is_function_call:
            fn_name = getattr(frame, "function_name", "unknown_function")
            tool_call_id = getattr(frame, "tool_call_id", f"call_{self._interception_count}")
            raw_args = getattr(frame, "arguments", {})

            # Parse arguments if passed as JSON string
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except Exception:
                    raw_args = {"raw": raw_args}

            logger.info(f"[{self._trace_id}] Intercepted function call: {fn_name} with args: {raw_args}")

            # Directive 5: Pause audio generation during sidecar guardrail validation
            self._is_audio_paused = True
            eval_start = time.perf_counter()

            eval_request = GuardrailEvaluationRequest(
                trace_id=self._trace_id,
                function_name=fn_name,
                arguments=raw_args if isinstance(raw_args, dict) else {},
            )

            try:
                eval_result: GuardrailEvaluationResult = await self._guardrail_service.evaluate_tool_call(eval_request)
                eval_duration_ms = round((time.perf_counter() - eval_start) * 1000, 2)
                self._total_overhead_ms += eval_duration_ms
                self._interception_count += 1

                if eval_result.violations:
                    for v in eval_result.violations:
                        self._violations_detected.append(f"[{v.policy_type.value}] {v.message}")
                        logger.warning(f"[{self._trace_id}] Policy violation: {v.message}")

                # Format deterministic response payload for the LLM
                if eval_result.action == GuardrailAction.BLOCK:
                    result_payload = {
                        "status": "error",
                        "error_code": "POLICY_VIOLATION",
                        "message": eval_result.feedback_to_agent or "This operation is prohibited by clinic policy.",
                    }
                elif eval_result.action == GuardrailAction.MODIFY:
                    result_payload = {
                        "status": "modified",
                        "message": eval_result.feedback_to_agent or "Parameters were sanitized and accepted.",
                        "sanitized_arguments": eval_result.arguments,
                    }
                else:
                    result_payload = {
                        "status": "success",
                        "message": eval_result.feedback_to_agent or "Action validated and processed successfully.",
                        "data": eval_result.arguments,
                    }

                # Directive 5: Inject FunctionCallResultFrame back into the pipeline
                result_frame = FunctionCallResultFrame(
                    function_name=fn_name,
                    tool_call_id=tool_call_id,
                    arguments=raw_args,
                    result=result_payload,
                )
                logger.debug(f"[{self._trace_id}] Injecting FunctionCallResultFrame: {result_payload}")
                await self.push_frame(result_frame, direction)

            finally:
                # Directive 5: Resume audio generation and flush any buffered frames
                self._is_audio_paused = False
                for held in self._held_audio_frames:
                    await self.push_frame(held, direction)
                self._held_audio_frames.clear()

            return

        # 2. Gate audio frames while policy evaluation is underway
        if self._is_audio_paused and isinstance(frame, (AudioRawFrame, TTSAudioRawFrame)):
            self._held_audio_frames.append(frame)
            return

        # 3. All other frames pass downstream without modification
        await self.push_frame(frame, direction)
