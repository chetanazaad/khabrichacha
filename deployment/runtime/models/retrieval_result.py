from typing import List, Dict, Any
from pydantic import BaseModel, Field

class CandidateSource(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    domain: str = ""
    rank_score: float = 0.0
    trust_score: float = 0.0
    is_duplicate: bool = False
    duplicate_reason: str = ""
    source_tool: str = ""          # "search_web" | "search_news"
    domain_category: str = "general" # "gov" | "edu" | "news" | etc.

class RetrievalResult(BaseModel):
    candidate_sources: List[CandidateSource] = Field(default_factory=list)
    ranked_sources: List[CandidateSource] = Field(default_factory=list)
    duplicate_sources: List[CandidateSource] = Field(default_factory=list)
    filtered_sources: List[CandidateSource] = Field(default_factory=list)
    estimated_quality: float = 0.0
    estimated_trust: float = 0.0
    recommended_fetch_count: int = 5
    search_time: float = 0.0
    dedup_time: float = 0.0
    rank_time: float = 0.0
    extracted_answer: str | None = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
