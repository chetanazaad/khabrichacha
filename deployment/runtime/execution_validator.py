import json
import os
from typing import Dict, Any, List

class ExecutionValidator:
    """
    Validates execution traces post-execution to ensure runtime pipelines
    followed strict strategy rules (e.g. Planner never runs on FAST).
    """

    STRATEGY_RULES = {
        "FAST": {
            "required": ["Retriever"],
            "forbidden": ["Planner", "ReportExporter", "KnowledgeGraph"]
        },
        "LOOKUP": {
            "required": ["Retriever"],
            "forbidden": ["Planner", "ReportExporter", "KnowledgeGraph"]
        },
        "STRUCTURED": {
            "required": ["Retriever"],
            "forbidden": ["Planner", "ReportExporter", "KnowledgeGraph"]
        },
        "COMPARISON": {
            "required": ["Retriever", "LLM Reasoning"],
            "forbidden": ["Planner", "ReportExporter", "KnowledgeGraph"]
        },
        "ANALYSIS": {
            "required": ["Retriever", "LLM Reasoning"],
            "forbidden": ["Planner", "ReportExporter", "KnowledgeGraph"]
        },
        "RESEARCH": {
            "required": ["Orchestrator", "ReportExporter"],
            "forbidden": []
        },
        "DEEP_RESEARCH": {
            "required": ["Orchestrator", "ReportExporter", "KnowledgeGraph"],
            "forbidden": []
        }
    }

    @staticmethod
    def validate_trace(trace: Dict[str, Any]) -> bool:
        """Validates a trace dict directly."""
        strategy = trace.get("strategy", "UNKNOWN").upper()
        if strategy not in ExecutionValidator.STRATEGY_RULES:
            # If strategy is not tracked or unknown, allow it for now.
            return True

        rules = ExecutionValidator.STRATEGY_RULES[strategy]
        
        executed = trace.get("initialization_order", [])
        skipped = list(trace.get("skipped_components", {}).keys())
        
        errors = []

        # Check forbidden
        for f in rules["forbidden"]:
            if f in executed and f not in skipped:
                errors.append(f"Forbidden component executed: {f} in strategy {strategy}")

        if errors:
            raise ValueError(f"Execution Validation Failed: {'; '.join(errors)}")
            
        return True

    @staticmethod
    def validate_trace_file(path: str) -> bool:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Trace file not found: {path}")
            
        with open(path, "r", encoding="utf-8") as f:
            trace = json.load(f)
            
        return ExecutionValidator.validate_trace(trace)
