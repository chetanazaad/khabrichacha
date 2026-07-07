from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ExecutionBudget(BaseModel):
    """Resource and rate limits for query execution to control cost/latency."""
    max_searches: int = Field(default=5, ge=0)
    max_fetches: int = Field(default=5, ge=0)
    max_sources: int = Field(default=10, ge=0)
    max_llm_calls: int = Field(default=3, ge=0)
    max_iterations: int = Field(default=5, ge=0)
    max_runtime_seconds: int = Field(default=300, ge=1)
    max_download_size_mb: int = Field(default=50, ge=1)

class ResearchStrategy(BaseModel):
    """Governs which pipeline stages are enabled and sets performance boundaries."""
    strategy_name: str          # FAST | LOOKUP | STRUCTURED | COMPARISON | ANALYSIS | RESEARCH | DEEP_RESEARCH
    intent: str                 # e.g., FACT_LOOKUP, STRUCTURED_DATA, COMPARISON, ANALYSIS, RESEARCH, DEEP_RESEARCH
    complexity: int = Field(default=1, ge=0, le=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Pipeline gates
    requires_planner: bool = False
    requires_llm: bool = True
    requires_search: bool = True
    requires_fetch: bool = True
    requires_pdf: bool = False
    requires_reasoning: bool = True
    requires_adaptive_loop: bool = False
    requires_evidence_evaluation: bool = False
    requires_report_generation: bool = False
    requires_summary: bool = False
    requires_structured_output: bool = False

    # Persistence gates
    allow_project_creation: bool = True
    allow_workspace_save: bool = True
    allow_report_generation: bool = True
    allow_evidence_collection: bool = True
    allow_summary_generation: bool = True
    allow_reasoning: bool = True
    allow_analysis: bool = True

    # Output & iteration preferences
    preferred_output: str = "direct_answer"  # "direct_answer" | "markdown_table" | "comparison_matrix" | "timeline" | "report_md"
    max_iterations: int = 5
    enabled_tools: List[str] = Field(default_factory=list)
    execution_budget: ExecutionBudget = Field(default_factory=ExecutionBudget)

    # Cost / Latency estimates
    estimated_latency_seconds: float = 10.0
    estimated_cost: str = "low"  # "free" | "low" | "medium" | "high"
