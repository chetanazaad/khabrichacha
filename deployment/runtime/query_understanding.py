from __future__ import annotations

import re
from typing import Any, Dict, Optional

from deployment.runtime.models.query_understanding import QueryUnderstanding


class QueryUnderstandingEngine:
    """Builds a lightweight Stage 1 understanding model from a mission string."""

    def __init__(self) -> None:
        self._answer_type_map = {
            "count": ["how many", "how often", "number of times", "count"],
            "list": ["list", "names", "examples", "types"],
            "comparison": ["vs", "versus", "difference between", "compare"],
            "analysis": ["why", "analyze", "explain", "impact", "implications"],
            "fact": ["who", "what", "where", "when", "capital", "president", "weather"],
        }

    def understand(self, mission: str) -> QueryUnderstanding:
        text = (mission or "").strip()
        if not text:
            return QueryUnderstanding(mission=text, answer_type="fact", confidence=0.0, rationale="Empty mission")

        lowered = text.lower()
        answer_type = "fact"
        constraints: Dict[str, Any] = {}
        ambiguity_flag = False
        rationale = ""
        strategy_hint = ""

        if any(token in lowered for token in [" vs ", " versus ", "difference between", "compare"]):
            answer_type = "comparison"
            rationale = "The mission asks for a comparison between entities or options."
            strategy_hint = "COMPARISON"
        elif any(token in lowered for token in ["how many", "how often", "number of times", "count of"]):
            answer_type = "count"
            rationale = "The mission asks for a count or frequency."
            strategy_hint = "STRUCTURED"
        elif any(token in lowered for token in ["list", "names", "examples", "types"]):
            answer_type = "list"
            rationale = "The mission asks for multiple items rather than a single fact."
            strategy_hint = "LOOKUP"
        elif any(token in lowered for token in ["why", "analyze", "explain", "impact", "implications"]):
            answer_type = "analysis"
            rationale = "The mission asks for reasoning or explanation."
            strategy_hint = "ANALYSIS"

        if len(text.split()) > 18:
            ambiguity_flag = True
            constraints["long_query"] = True
        if re.search(r"\b(near|recent|latest|current|today|now)\b", lowered):
            constraints["time_sensitive"] = True
        if re.search(r"\b(between|before|after|since|until|during)\b", lowered):
            constraints["temporal"] = True
        if re.search(r"\b(and|or)\b", lowered):
            constraints["multi_entity"] = True

        confidence = 0.7 if not ambiguity_flag else 0.55
        if answer_type != "fact":
            confidence = min(0.95, confidence + 0.15)
        if strategy_hint:
            confidence = min(0.95, confidence + 0.05)

        return QueryUnderstanding(
            mission=text,
            answer_type=answer_type,
            ambiguity_flag=ambiguity_flag,
            confidence=confidence,
            constraints=constraints,
            rationale=rationale or "The mission was categorized as a direct fact lookup.",
            strategy_hint=strategy_hint or "LOOKUP",
        )
