from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Entity(BaseModel):
    name: str
    normalized_name: str
    entity_type: str = ""           # "person" | "organization" | "country" | "concept" | etc.
    aliases: List[str] = Field(default_factory=list)

class Claim(BaseModel):
    statement: str
    source_url: str = ""
    confidence: float = 1.0
    evidence: str = ""

class Metric(BaseModel):
    name: str
    value: Any
    unit: str = ""
    period: str = ""
    source: str = ""

class Relation(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0

class KnowledgeObjects(BaseModel):
    """Normalized structured objects generated before reasoning."""
    entities: List[Entity] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    metrics: List[Metric] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
