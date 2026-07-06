from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator

class ResearchRequest(BaseModel):
    """Standardized request to start a research run."""
    mission: str
    provider: str
    model: str
    depth: str = "standard"
    max_iterations: int = Field(default=5, ge=1)
    enabled_tools: List[str] = Field(default_factory=list)
    output_formats: List[str] = Field(default_factory=lambda: ["md", "json", "pdf"])
    workspace: str
    project_id: Optional[str] = None
    resume: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("mission")
    @classmethod
    def mission_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Mission cannot be empty.")
        return v
        
    @field_validator("provider")
    @classmethod
    def provider_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Provider must be specified.")
        return v

    @field_validator("model")
    @classmethod
    def model_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Model must be specified.")
        return v
        
    @field_validator("output_formats")
    @classmethod
    def output_formats_supported(cls, v: List[str]) -> List[str]:
        supported = {"md", "json", "pdf"}
        for fmt in v:
            if fmt not in supported:
                raise ValueError(f"Output format '{fmt}' is not supported.")
        return v

    @model_validator(mode='after')
    def validate_resume(self):
        if self.resume and not self.project_id:
            raise ValueError("project_id must exist when resume=True")
        return self
