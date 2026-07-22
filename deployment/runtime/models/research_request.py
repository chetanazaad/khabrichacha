from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator

class ResearchRequest(BaseModel):
    """Standardized request to start a research run."""
    mission: str
    provider: str
    model: str
    ingestion_provider: Optional[str] = None
    ingestion_model: Optional[str] = None
    analysis_provider: Optional[str] = None
    analysis_model: Optional[str] = None
    depth: str = "standard"
    max_iterations: int = Field(default=5, ge=1)
    enabled_tools: List[str] = Field(default_factory=list)
    output_formats: List[str] = Field(default_factory=lambda: ["md", "json", "pdf", "docx"])
    workspace: str
    project_id: Optional[str] = None
    resume: bool = False
    strategy_override: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def set_dual_model_defaults(self):
        if not self.ingestion_provider:
            self.ingestion_provider = self.provider
        if not self.ingestion_model:
            self.ingestion_model = self.model
        if not self.analysis_provider:
            self.analysis_provider = self.provider
        if not self.analysis_model:
            self.analysis_model = self.model
        return self

    
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
        supported = {"md", "json", "pdf", "docx", "txt"}
        for fmt in v:
            if fmt not in supported:
                raise ValueError(f"Output format '{fmt}' is not supported.")
        return v

    @model_validator(mode='after')
    def validate_resume(self):
        if self.resume and not self.project_id:
            raise ValueError("project_id must exist when resume=True")
        return self
