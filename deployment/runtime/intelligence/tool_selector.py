from typing import List, Dict, Any
from pydantic import BaseModel, Field
from deployment.runtime.models.research_strategy import ResearchStrategy

class ToolRecommendation(BaseModel):
    primary: str = ""
    fallback: str = ""
    parallel: List[str] = Field(default_factory=list)
    retry: List[str] = Field(default_factory=list)

class ToolSelector:
    """Intelligently scores and selects appropriate tools based on domain, latency targets, and budget."""

    def select(self, query: str, strategy: ResearchStrategy, available_tools: List[str]) -> ToolRecommendation:
        cleaned_query = query.lower()
        
        # Tools we support checking
        # ["search_web", "search_news", "fetch_page", "fetch_pdf", "python_executor"]

        # Default recommendations
        rec = ToolRecommendation()

        # 1. Determine fetch/search tools
        if "gov" in cleaned_query or "budget" in cleaned_query:
            # High suitability for official search
            if "search_web" in available_tools:
                rec.primary = "search_web"
                rec.fallback = "search_news"
            if "fetch_page" in available_tools:
                rec.parallel.append("fetch_page")
            if "fetch_pdf" in available_tools:
                rec.retry.append("fetch_pdf")  # Retry with PDF if normal page fails
        elif "news" in cleaned_query or "latest" in cleaned_query or "today" in cleaned_query:
            if "search_news" in available_tools:
                rec.primary = "search_news"
                rec.fallback = "search_web"
            else:
                rec.primary = "search_web"
            if "fetch_page" in available_tools:
                rec.parallel.append("fetch_page")
        else:
            if "search_web" in available_tools:
                rec.primary = "search_web"
                rec.fallback = "search_news"
            if "fetch_page" in available_tools:
                rec.parallel.append("fetch_page")

        # 2. Check for python executor suitability (e.g. calculation, chart, percentage, growth)
        if any(term in cleaned_query for term in ["calculate", "sum", "average", "percentage", "growth", "cagr", "total"]):
            if "python_executor" in available_tools:
                rec.parallel.append("python_executor")

        # Fill defaults if primary is empty
        if not rec.primary and available_tools:
            rec.primary = available_tools[0]
        if not rec.fallback and len(available_tools) > 1:
            rec.fallback = available_tools[1]

        return rec
