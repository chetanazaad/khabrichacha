import time
import re
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
from loguru import logger
from deployment.workspace.workspace_manager import WorkspaceManager
from deployment.runtime.retrieval.workspace_index import WorkspaceIndex

class KnowledgeResult(BaseModel):
    """Result of searching the local hybrid knowledge layers before web search."""
    reusable_content: List[Dict[str, Any]] = Field(default_factory=list)
    needs_web_search: bool = True
    retrieval_source: str = "none" # "workspace_memory" | "cache" | "local_knowledge" | "web"
    confidence: float = 0.0
    cache_hit_reason: str = ""
    retrieval_latency: float = 0.0

class KnowledgeRetriever:
    """Manages the 7-priority layer retrieval process."""

    def __init__(self, workspace_manager: WorkspaceManager):
        self.workspace = workspace_manager
        self.index = WorkspaceIndex(workspace_manager)

    def retrieve_local(self, query: str) -> KnowledgeResult:
        """
        Runs local hybrid knowledge retrieval across workspace, cache, and local layers.
        Returns KnowledgeResult.
        """
        start_time = time.time()
        cleaned_query = query.strip().lower()

        # Layer 6: Local Knowledge (deterministic facts)
        # Check simple local static knowledge first (e.g. capitals, country indicators, math formulas)
        local_content = self._check_local_knowledge(cleaned_query)
        if local_content:
            latency = time.time() - start_time
            return KnowledgeResult(
                reusable_content=[local_content],
                needs_web_search=False,
                retrieval_source="local_knowledge",
                confidence=0.99,
                cache_hit_reason="Exact match in local deterministic facts.",
                retrieval_latency=latency
            )

        # Layer 1 & 2: Workspace Memory & Cache
        # Search previous projects
        project_matches = self.index.search_projects(query)
        if project_matches:
            best_match = project_matches[0]
            if best_match["relevance_score"] >= 80:  # High confidence reuse
                reusable = []
                for m in project_matches[:3]:
                    reusable.append({
                        "title": m["title"],
                        "content": "\n".join(m["findings"]) + "\n" + m["report_content"],
                        "source": f"Workspace Project: {m['title']}"
                    })
                latency = time.time() - start_time
                return KnowledgeResult(
                    reusable_content=reusable,
                    needs_web_search=False,
                    retrieval_source="workspace_memory",
                    confidence=best_match["relevance_score"] / 100.0,
                    cache_hit_reason=f"Found high relevance project match: '{best_match['title']}'",
                    retrieval_latency=latency
                )

        # Layer 3 & 4: Research Cache / Downloaded Assets
        cache_matches = self.index.search_cache(query)
        if cache_matches:
            best_match = cache_matches[0]
            if best_match["relevance_score"] >= 85:
                reusable = []
                for m in cache_matches[:3]:
                    reusable.append({
                        "title": m["title"],
                        "content": m["content"],
                        "source": f"Cached Asset: {m['url']}"
                    })
                latency = time.time() - start_time
                return KnowledgeResult(
                    reusable_content=reusable,
                    needs_web_search=False,
                    retrieval_source="cache",
                    confidence=best_match["relevance_score"] / 100.0,
                    cache_hit_reason=f"Found high relevance cached asset: '{best_match['title']}'",
                    retrieval_latency=latency
                )

        # Default: local layers insufficient, proceed to web
        latency = time.time() - start_time
        return KnowledgeResult(
            reusable_content=[],
            needs_web_search=True,
            retrieval_source="web",
            confidence=0.0,
            cache_hit_reason="No high confidence local match found. Proceeding to web search.",
            retrieval_latency=latency
        )

    def _check_local_knowledge(self, query: str) -> Optional[Dict[str, Any]]:
        """Simple deterministic factual mappings for common basic questions."""
        # Math match (handled by query classifier, but added here for redundancy)
        if re.match(r'^\d[\d\s\+\-\*\/\.\(\)]+$', query):
            try:
                # Safe eval limit to digits and operators
                res = str(eval(query, {"__builtins__": None}, {}))
                return {
                    "title": "Mathematical Calculation",
                    "content": f"The result of {query} is {res}.",
                    "source": "local_calculator"
                }
            except:
                pass

        # Static capitals
        capitals = {
            "capital of japan": "Tokyo",
            "capital of india": "New Delhi",
            "capital of france": "Paris",
            "capital of germany": "Berlin",
            "capital of uk": "London",
            "capital of united kingdom": "London",
            "capital of usa": "Washington, D.C.",
            "capital of united states": "Washington, D.C.",
            "capital of italy": "Rome",
            "capital of spain": "Madrid",
            "capital of canada": "Ottawa",
            "capital of australia": "Canberra"
        }
        for k, v in capitals.items():
            if k in query:
                return {
                    "title": f"Capital of {k.split('of ')[1].title()}",
                    "content": f"The capital of {k.split('of ')[1].title()} is {v}.",
                    "source": "local_database"
                }

        return None
