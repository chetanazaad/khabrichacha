from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from deployment.runtime.models.research_statistics import ResearchStatistics
from deployment.runtime.models.error_info import ErrorInfo

class ResearchResult(BaseModel):
    """Standardized response from ResearchController."""
    success: bool = False
    project_id: str = ""
    project_path: str = ""
    provider: str = ""
    model: str = ""
    iterations: int = 0
    report_md_path: str = ""
    report_json_path: str = ""
    report_pdf_path: str = ""
    report_docx_path: str = ""
    report_txt_path: str = ""
    statistics: ResearchStatistics = Field(default_factory=ResearchStatistics)
    evidence_count: int = 0
    source_count: int = 0
    elapsed_time: float = 0.0
    errors: List[ErrorInfo] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)
    
    # New fields for Strategy/Intelligence routing
    strategy_used: str = ""
    direct_answer: str = ""
    classification_time: float = 0.0
    strategy_confidence: float = 0.0
    retrieval_stats: Dict[str, Any] = Field(default_factory=dict)
    trust_scores: List[Dict[str, float]] = Field(default_factory=list)
    output_format: str = ""

