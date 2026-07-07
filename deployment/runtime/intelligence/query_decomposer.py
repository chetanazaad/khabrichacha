import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from deployment.runtime.models.research_strategy import ResearchStrategy

class Subtask(BaseModel):
    id: str
    description: str
    depends_on: List[str] = Field(default_factory=list)

class DecomposedQuery(BaseModel):
    original: str
    subtasks: List[Subtask] = Field(default_factory=list)
    is_complex: bool = False
    synthesis_needed: bool = False

class QueryDecomposer:
    """Decomposes complex, multi-part research queries into independent, manageable subtasks."""

    def decompose(self, query: str, strategy: ResearchStrategy) -> DecomposedQuery:
        cleaned = query.strip().lower()
        
        # Default decomposition: single task
        dq = DecomposedQuery(original=query)
        
        # 1. Comparison query decomposition
        if strategy.strategy_name == "COMPARISON" or " vs " in cleaned or "compare " in cleaned:
            # Try to identify entities
            entities = self._extract_comparison_entities(cleaned)
            if len(entities) >= 2:
                dq.is_complex = True
                dq.synthesis_needed = True
                dq.subtasks = [
                    Subtask(id="1", description=f"Collect detailed profiles and specifications for {entities[0]}."),
                    Subtask(id="2", description=f"Collect detailed profiles and specifications for {entities[1]}."),
                    Subtask(id="3", description=f"Compare {entities[0]} vs {entities[1]} across key parameters.", depends_on=["1", "2"]),
                    Subtask(id="4", description="Synthesize findings and compile comparison matrix.", depends_on=["3"])
                ]
                return dq

        # 2. Structured/analysis query decomposition (e.g. "budget from 2020-2025 and explain why")
        if "budget" in cleaned and ("explain" in cleaned or "why" in cleaned or "reason" in cleaned):
            dq.is_complex = True
            dq.synthesis_needed = True
            dq.subtasks = [
                Subtask(id="1", description="Collect annual budget allocations and figures."),
                Subtask(id="2", description="Compute year-over-year growth rates and normalize currencies."),
                Subtask(id="3", description="Identify policy events and macroeconomic reasons for spending shifts.", depends_on=["1", "2"]),
                Subtask(id="4", description="Synthesize numbers with narrative explanations.", depends_on=["3"])
            ]
            return dq

        # Simple default decomposition
        dq.subtasks = [
            Subtask(id="1", description=f"Search and fetch relevant information for: {query}")
        ]
        return dq

    def _extract_comparison_entities(self, query: str) -> List[str]:
        # Split by "vs" or "versus"
        parts = []
        if " vs " in query:
            parts = query.split(" vs ")
        elif " versus " in query:
            parts = query.split(" versus ")
        
        if len(parts) >= 2:
            return [p.strip().title() for p in parts]
            
        # Match "compare X and Y"
        match = re.search(r'compare\s+([\w\s]+)\s+and\s+([\w\s]+)', query)
        if match:
            return [match.group(1).strip().title(), match.group(2).strip().title()]
            
        return []
