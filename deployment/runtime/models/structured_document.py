from typing import List, Dict, Any
from pydantic import BaseModel, Field

class StructuredDocument(BaseModel):
    """Holds parsed and normalized structured tables or key-value data extracted from fetched files."""
    document_type: str = "text"              # "table" | "json" | "csv" | "text" | "mixed"
    title: str = ""
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_url: str = ""
    confidence: float = 1.0
    normalized_json: Dict[str, Any] = Field(default_factory=dict)
    raw_content: str = ""
    is_structured: bool = False
