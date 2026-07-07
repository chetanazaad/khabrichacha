import json
import os
import time
from typing import Dict, Any, List
from loguru import logger

class ExecutionTraceRecorder:
    """
    Records an end-to-end trace of a single research query execution.
    For debugging and verification. Does not alter runtime behavior.
    """

    def __init__(self, project_path: str = ""):
        self.project_path = project_path
        self.trace_data: Dict[str, Any] = {
            "query": "",
            "strategy": "",
            "confidence": 0.0,
            "complexity_score": 0,
            "consensus_score": 0.0,
            "staged_retrieval_timings": {},
            "modules_executed": [],
            "modules_skipped": [],
            "module_times": {},
            "skip_reasons": {},
            "llm_audit": {
                "invoked": False,
                "reasoning_skipped": False,
                "calls": 0,
                "provider": "",
                "model": "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cache_reuse": 0
            },
            "retrieval_audit": {
                "searched_domains": [],
                "sources_returned": 0,
                "duplicates_removed": 0,
                "trusted_sources": 0,
                "discarded_sources": 0,
                "official_sources_detected": 0
            },
            "start_time": time.time(),
            "end_time": None
        }

    def set_query_info(self, query: str, strategy: str, confidence: float, complexity: int = 0):
        self.trace_data["query"] = query
        self.trace_data["strategy"] = strategy
        self.trace_data["confidence"] = confidence
        self.trace_data["complexity_score"] = complexity

    def record_runtime_info(self, config_source: str = "", tool_registry_source: str = "", session_created: bool = True):
        self.trace_data["runtime_info"] = {
            "config_source": config_source,
            "tool_registry_source": tool_registry_source,
            "session_created": session_created,
        }

    def record_consensus(self, score: float):
        self.trace_data["consensus_score"] = score

    def record_staged_timing(self, stage: str, time_ms: float):
        self.trace_data["staged_retrieval_timings"][stage] = time_ms

    def record_module(self, name: str, execution_time_ms: float = 0.0, skipped: bool = False, reason: str = ""):
        if skipped:
            if name not in self.trace_data["modules_skipped"]:
                self.trace_data["modules_skipped"].append(name)
            self.trace_data["skip_reasons"][name] = reason
        else:
            if name not in self.trace_data["modules_executed"]:
                self.trace_data["modules_executed"].append(name)
            self.trace_data["module_times"][name] = execution_time_ms

    def record_llm_call(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int, cached: bool = False, skip_reason: str = ""):
        audit = self.trace_data["llm_audit"]
        if skip_reason:
            audit["reasoning_skipped"] = True
            self.trace_data["skip_reasons"]["LLM Reasoning"] = skip_reason
            return
            
        audit["invoked"] = True
        audit["calls"] += 1
        audit["provider"] = provider
        audit["model"] = model
        audit["prompt_tokens"] += prompt_tokens
        audit["completion_tokens"] += completion_tokens
        if cached:
            audit["cache_reuse"] += 1

    def record_retrieval(self, returned: int, duplicates: int, trusted: int, discarded: int, official: int, domains: List[str]):
        audit = self.trace_data["retrieval_audit"]
        audit["sources_returned"] += returned
        audit["duplicates_removed"] += duplicates
        audit["trusted_sources"] += trusted
        audit["discarded_sources"] += discarded
        audit["official_sources_detected"] += official
        audit["searched_domains"] = list(set(audit["searched_domains"] + domains))

    def dump_trace(self) -> Dict[str, Any]:
        self.trace_data["end_time"] = time.time()
        self.trace_data["total_time_ms"] = (self.trace_data["end_time"] - self.trace_data["start_time"]) * 1000

        # Save to disk
        if self.project_path:
            os.makedirs(self.project_path, exist_ok=True)
            trace_path = os.path.join(self.project_path, "trace.json")
            try:
                with open(trace_path, "w", encoding="utf-8") as f:
                    json.dump(self.trace_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to write trace.json: {e}")

        return self.trace_data
