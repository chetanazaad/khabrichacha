from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class QueryUnderstanding(BaseModel):
    """Stage 1 query understanding output used for deterministic routing and verification."""

    mission: str
    answer_type: str = "fact"
    ambiguity_flag: bool = False
    confidence: float = 0.0
    constraints: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    strategy_hint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer_type": self.answer_type,
            "ambiguity_flag": self.ambiguity_flag,
            "confidence": round(self.confidence, 2),
            "constraints": self.constraints,
            "rationale": self.rationale,
            "strategy_hint": self.strategy_hint,
        }
