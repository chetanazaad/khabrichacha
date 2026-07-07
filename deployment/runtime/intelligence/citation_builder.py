from typing import List, Dict, Any
from pydantic import BaseModel, Field
from urllib.parse import urlparse
from datetime import datetime

class Citation(BaseModel):
    index: int
    title: str = ""
    url: str
    domain: str = ""
    trust_score: float = 50.0
    accessed_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class CitationBuilder:
    """Consolidates search/fetch references into clean, indexed, and deduplicated citation lists."""

    def build(self, sources: List[Dict[str, Any]]) -> List[Citation]:
        citations = []
        seen_urls = set()
        index = 1

        for s in sources:
            url = s.get("url", "").strip()
            if not url:
                continue

            # Normalized url for dedup check
            from deployment.runtime.retrieval.deduplicator import Deduplicator
            norm_url = Deduplicator.clean_url(url)
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            # Determine domain
            try:
                domain = urlparse(url).netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = "unknown"

            title = s.get("title", "").strip() or f"Source from {domain}"
            trust = s.get("trust_score", 50.0)

            citations.append(Citation(
                index=index,
                title=title,
                url=url,
                domain=domain,
                trust_score=trust
            ))
            index += 1

        return citations

    def to_markdown(self, citations: List[Citation]) -> str:
        if not citations:
            return "_No citations collected._"
            
        lines = ["### References & Citations\n"]
        for c in citations:
            lines.append(f"{c.index}. **[{c.title}]({c.url})** (Domain: `{c.domain}`, Trust Score: `{c.trust_score:.0f}/100`)")
        return "\n".join(lines)

    def to_json(self, citations: List[Citation]) -> List[Dict[str, Any]]:
        return [c.model_dump() for c in citations]
