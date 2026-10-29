"""Validated, portable specifications for architecture experiments."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Architecture = Literal["buffered", "text_buffered", "audio_buffered", "streaming", "guarded"]


class ExperimentSpec(BaseModel):
    modes: list[Architecture] = Field(default_factory=lambda: ["buffered", "streaming", "guarded"], min_length=1, max_length=5)
    repeats: int = Field(default=1, ge=1, le=30)
    warmup: bool = False
    order_offset: int = Field(default=0, ge=0, le=4)
    task: Literal["conversation", "knowledge", "extraction", "action"] = "conversation"
    instruction: str = Field(default="Answer clearly in two or three short sentences.", max_length=2000)
    context: str = Field(default="", max_length=6000)
    expected_phrase: str = Field(default="", max_length=200)
    required_facts: list[str] = Field(default_factory=list, max_length=20)
    acceptable_facts: list[list[str]] = Field(default_factory=list, max_length=20)
    forbidden_facts: list[str] = Field(default_factory=list, max_length=20)
    expected_fields: dict[str, str] = Field(default_factory=dict, max_length=20)
    expected_action: str = Field(default="", max_length=40)
    expected_amount: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    expected_tool_status: Literal["", "blocked", "simulated"] = ""
    action_limit: float = Field(default=100, ge=0, le=10000, allow_inf_nan=False)
    allowed_actions: list[str] = Field(default_factory=lambda: ["refund", "credit", "reserve"], max_length=10)

    @model_validator(mode="after")
    def unique_modes(self):
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("Choose each architecture once.")
        if any(not name or len(name) > 40 for name in self.allowed_actions):
            raise ValueError("Action names must contain 1–40 characters.")
        if any(not s.strip() or len(s) > 200 for s in self.required_facts + self.forbidden_facts):
            raise ValueError("Facts must contain 1–200 characters.")
        if any(not group or len(group) > 5 or any(not s.strip() or len(s) > 200 for s in group) for group in self.acceptable_facts):
            raise ValueError("Use 1–5 nonempty alternatives of up to 200 characters per fact.")
        if any(not k or len(k) > 80 or len(v) > 200 for k, v in self.expected_fields.items()):
            raise ValueError("Expected fields are too long.")
        return self

    def schedule(self):
        # Rotate order each repetition to distribute first-run/provider warm-up effects.
        warmup = [(0, mode) for mode in self.modes] if self.warmup else []
        n = len(self.modes)
        return warmup + [(trial + 1, mode) for trial in range(self.repeats)
                for mode in self.modes[(trial+self.order_offset) % n:] + self.modes[:(trial+self.order_offset) % n]]
