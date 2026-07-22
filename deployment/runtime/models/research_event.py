from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ResearchEvent(BaseModel):
    """An event emitted during a research run."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    level: str = "INFO"  # INFO, WARNING, ERROR, DEBUG
    component: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
