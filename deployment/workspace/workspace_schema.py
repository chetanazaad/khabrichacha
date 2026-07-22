"""
deployment/workspace/workspace_schema.py

Pydantic schema for everything persisted under a project directory:
manifests, runtime/research/planner state snapshots, and the reference
(citation) index. Rebuilt after these were found to be missing from the
repository (an unanchored ".gitignore" rule was silently excluding the
whole deployment/workspace/ package — see .gitignore for the fix).

These models are intentionally permissive (`extra="allow"`) where they
mirror ad-hoc dictionaries elsewhere in the codebase (e.g. Session.research_state
in khabrichacha/core/session.py), so a new key added there doesn't break
persistence here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class ProjectManifest(BaseModel):
    """Top-level metadata for a single research project/session."""
    model_config = ConfigDict(extra="allow")

    project_id: str
    title: str = ""
    mission: str = ""
    provider: str = ""
    model: str = ""
    research_depth: str = "standard"
    is_temp: bool = False
    status: str = "created"  # created, running, completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    iterations: int = 0
    source_count: int = 0
    evidence_count: int = 0
    locked: bool = False


class RuntimeState(BaseModel):
    """Lightweight snapshot of Session.runtime (ad-hoc scratch variables)."""
    model_config = ConfigDict(extra="allow")

    session_id: str = ""
    variables: Dict[str, Any] = Field(default_factory=dict)


class ResearchState(BaseModel):
    """
    Mirrors khabrichacha.core.session.Session.research_state.
    Field names/defaults match that dict exactly; `extra="allow"` protects
    against future keys added there without a matching change here.
    """
    model_config = ConfigDict(extra="allow")

    iteration: int = 0
    completed: bool = False
    total_sources: int = 0
    unique_domains: int = 0
    findings: List[str] = Field(default_factory=list)
    coverage: str = "0%"
    outstanding_questions: List[str] = Field(default_factory=list)


class PlannerState(BaseModel):
    """Snapshot of the adaptive planner's step list at save time."""
    model_config = ConfigDict(extra="allow")

    steps: List[Any] = Field(default_factory=list)


class ReferenceEntry(BaseModel):
    """A single citation/source reference."""
    model_config = ConfigDict(extra="allow")

    title: str = ""
    url: str = ""
    domain: str = ""
    trust_score: float = 50.0


class ReferenceIndex(BaseModel):
    """Collection of reference entries for a project."""
    model_config = ConfigDict(extra="allow")

    entries: List[ReferenceEntry] = Field(default_factory=list)
    total: int = 0
