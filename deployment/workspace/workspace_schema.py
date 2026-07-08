"""
KhabriChacha — Workspace Schema

Strongly typed Pydantic models for every project file.
All filesystem reads/writes go through these models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class ProjectManifest(BaseModel):
    """The project.json manifest stored at the root of every project."""
    project_version: int = 1
    engine_version: str = "1.0.0"
    schema_version: str = "1.0"
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = ""
    mission: str = ""
    provider: str = ""
    model: str = ""
    research_depth: str = "standard"
    status: str = "created"       # created | running | completed | failed | locked
    created: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    iterations: int = 0
    reports: List[str] = Field(default_factory=lambda: ["report.md", "report.json", "report.pdf"])
    runtime_file: str = "runtime.json"
    planner_file: str = "planner.json"
    research_state_file: str = "research_state.json"
    reference_file: str = "references.json"
    evidence_count: int = 0
    source_count: int = 0


class ProjectSettings(BaseModel):
    """Per-project settings restored when a project is reopened."""
    provider: str = ""
    model: str = ""
    research_depth: str = "standard"
    max_iterations: int = 5
    parallel_fetch: int = 10
    language: str = "English"
    output_formats: List[str] = Field(default_factory=lambda: ["md", "json", "pdf"])


class ProjectMetadata(BaseModel):
    """Extra metadata about a project."""
    created_by: str = "KhabriChacha"
    engine_version: str = "1.0.0"
    platform: str = ""
    notes: str = ""
    tags: List[str] = Field(default_factory=list)


class RuntimeState(BaseModel):
    """Serialized runtime variable state."""
    session_id: str = ""
    variables: Dict[str, Any] = Field(default_factory=dict)
    iteration_summaries: Dict[str, str] = Field(default_factory=dict)


class ResearchState(BaseModel):
    """Serialized research progress state."""
    iteration: int = 0
    completed: bool = False
    total_sources: int = 0
    unique_domains: int = 0
    findings: List[str] = Field(default_factory=list)
    coverage: str = "0%"
    outstanding_questions: List[str] = Field(default_factory=list)


class PlannerState(BaseModel):
    """Serialized planner output."""
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    adaptive_history: List[Dict[str, Any]] = Field(default_factory=list)


class EvidenceDocument(BaseModel):
    """A single piece of evidence preserving raw, clean, and summary layers."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = ""
    url: str = ""
    publisher: str = ""
    author: str = ""
    published: str = ""
    language: str = "English"
    content_type: str = "text/html"
    raw_path: str = ""
    clean_path: str = ""
    summary_path: Optional[str] = None
    metadata_path: str = ""
    hash: str = ""
    created: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: str = "RAW_ONLY"  # RAW_ONLY | CLEAN_READY | SUMMARY_READY


class EvidenceIndex(BaseModel):
    """Index of all collected evidence documents."""
    entries: List[EvidenceDocument] = Field(default_factory=list)
    total: int = 0


class ReferenceEntry(BaseModel):
    """A single reference/source."""
    title: str = ""
    url: str = ""
    source: str = ""
    accessed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReferenceIndex(BaseModel):
    """Index of all references."""
    entries: List[ReferenceEntry] = Field(default_factory=list)
    total: int = 0
