from typing import Dict, Any
from pydantic import BaseModel, Field

class ResearchStatistics(BaseModel):
    """Execution statistics for a research run."""
    elapsed_time: float = 0.0
    iterations: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    downloaded_sources: int = 0
    cached_sources: int = 0
    assets_created: int = 0
    evidence_documents: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    errors: int = 0
    warnings: int = 0
    
    # Extended metrics
    total_execution_time: float = 0.0
    average_tool_execution_time: float = 0.0
    average_llm_response_time: float = 0.0
    provider_latency: float = 0.0
    total_download_size: int = 0
    cache_saved_downloads: int = 0
    cache_saved_tokens: int = 0

    # New timing and metrics for Strategy/Intelligence (v1.4, v1.5, v1.6)
    classification_time: float = 0.0
    strategy_time: float = 0.0
    planner_time: float = 0.0
    search_time: float = 0.0
    fetch_time: float = 0.0
    reasoning_time: float = 0.0
    report_time: float = 0.0
    retrieval_time: float = 0.0
    dedup_time: float = 0.0
    ranking_time: float = 0.0
    trust_eval_time: float = 0.0
    extraction_time: float = 0.0
    consensus_time: float = 0.0
    entity_resolution_time: float = 0.0
    temporal_resolution_time: float = 0.0
    context_optimization_time: float = 0.0
    response_planning_time: float = 0.0
    
    strategy_selected: str = ""
    strategy_confidence: float = 0.0
    execution_budget_used: Dict[str, Any] = Field(default_factory=dict)
    execution_budget_remaining: Dict[str, Any] = Field(default_factory=dict)
    sources_downloaded: int = 0
    sources_cached: int = 0
    sources_deduplicated: int = 0
    sources_trusted: int = 0
    planner_calls: int = 0
    adaptive_iterations: int = 0
    knowledge_cache_hits: int = 0
    output_format_selected: str = ""
    model_selected: str = ""
    
    # Audit & Tracing (v1.8)
    trace_data: Dict[str, Any] = Field(default_factory=dict)
    llm_audit: Dict[str, Any] = Field(default_factory=dict)
    retrieval_audit: Dict[str, Any] = Field(default_factory=dict)
    quality_scores: Dict[str, Any] = Field(default_factory=dict)
