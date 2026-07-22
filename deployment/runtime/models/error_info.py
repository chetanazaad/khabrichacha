from datetime import datetime
from pydantic import BaseModel, Field

class ErrorInfo(BaseModel):
    """Structured error information."""
    code: str = ""
    component: str = ""
    message: str = ""
    details: str = ""
    recoverable: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
