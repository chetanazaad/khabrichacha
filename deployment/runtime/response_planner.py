from pydantic import BaseModel, Field
from typing import List, Dict, Any
from deployment.runtime.models.research_strategy import ResearchStrategy
from deployment.runtime.models.structured_document import StructuredDocument

class ResponsePlan(BaseModel):
    """Configuration for formatting the final answer response."""
    output_format: str = "paragraph" # "paragraph" | "table" | "comparison" | "timeline" | "bullet_list" | "json" | "csv" | "summary" | "report"
    include_sources: bool = True
    include_trust_scores: bool = True
    include_structured_data: bool = True
    max_length: int = 1500

class ResponsePlanner:
    """Intelligently maps strategy and extracted documents into an optimal output format layout."""

    def plan(self, strategy: ResearchStrategy, docs: List[StructuredDocument], query: str) -> ResponsePlan:
        cleaned_query = query.lower()
        
        plan = ResponsePlan(
            include_sources=True,
            include_trust_scores=True
        )

        # 1. Check strategy override format
        if strategy.preferred_output == "markdown_table":
            plan.output_format = "table"
            return plan
        elif strategy.preferred_output == "comparison_matrix":
            plan.output_format = "comparison"
            return plan
        elif strategy.preferred_output == "report_md":
            plan.output_format = "report"
            return plan

        # 2. Check document extraction characteristics
        has_table = any(d.document_type in ["table", "csv"] and d.is_structured for d in docs)
        has_weather = any(d.document_type == "weather" for d in docs)
        
        if has_table:
            plan.output_format = "table"
            return plan

        if has_weather:
            plan.output_format = "summary"
            return plan

        # 3. Keyword/Intent heuristics
        if "timeline" in cleaned_query or "history of" in cleaned_query or "chronology" in cleaned_query:
            plan.output_format = "timeline"
            return plan

        if "list" in cleaned_query or "steps to" in cleaned_query or "how to" in cleaned_query:
            plan.output_format = "bullet_list"
            return plan

        if " vs " in cleaned_query or "compare" in cleaned_query or "difference between" in cleaned_query:
            plan.output_format = "comparison"
            return plan

        # 4. Simple question vs Analysis
        if strategy.strategy_name == "FAST":
            plan.output_format = "paragraph"
            plan.max_length = 500
        elif strategy.strategy_name == "LOOKUP":
            plan.output_format = "paragraph"
            plan.max_length = 800
        elif strategy.strategy_name == "ANALYSIS":
            plan.output_format = "summary"
            plan.max_length = 1500
        else:
            plan.output_format = "report"

        return plan
