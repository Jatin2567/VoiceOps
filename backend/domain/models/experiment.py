"""Validated, portable specifications for architecture experiments."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Architecture = Literal["buffered", "streaming", "guarded"]


class ExperimentSpec(BaseModel):
    modes: list[Architecture] = Field(default_factory=lambda: ["buffered", "streaming", "guarded"], min_length=1, max_length=3)
    repeats: int = Field(default=1, ge=1, le=3)
    task: Literal["conversation", "knowledge", "extraction", "action"] = "conversation"
    instruction: str = Field(default="Answer clearly in two or three short sentences.", max_length=2000)
    context: str = Field(default="", max_length=6000)
    expected_phrase: str = Field(default="", max_length=200)
    action_limit: float = Field(default=100, ge=0, le=10000, allow_inf_nan=False)
    allowed_actions: list[str] = Field(default_factory=lambda: ["refund", "credit", "reserve"], max_length=10)

    @model_validator(mode="after")
    def unique_modes(self):
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("Choose each architecture once.")
        if any(not name or len(name) > 40 for name in self.allowed_actions):
            raise ValueError("Action names must contain 1–40 characters.")
        return self

    def schedule(self):
        # Rotate order each repetition to distribute first-run/provider warm-up effects.
        return [(trial + 1, mode) for trial in range(self.repeats)
                for mode in self.modes[trial % len(self.modes):] + self.modes[:trial % len(self.modes)]]
