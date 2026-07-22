from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ConsensusResult(BaseModel):
    """Holds details of running multi-source consensus check on data points."""
    claim: str
    agreement_percentage: float = 0.0    # 0.0 to 100.0
    agreeing_sources: List[str] = Field(default_factory=list)
    conflicting_sources: List[str] = Field(default_factory=list)
    weighted_value: Optional[Any] = None  # Resolved consensus value
    confidence: float = 0.0               # Overall consensus confidence 0.0 to 1.0
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    resolution: str = "unresolved"         # "majority" | "weighted_average" | "unresolved"
