import re
from typing import List, Optional
from loguru import logger

class OfficialSourceResolver:
    """
    Identifies queries that require highly authoritative or official data
    (e.g., regulations, government statistics) and appends domain filters
    to search queries to prioritize these sources.
    """

    def __init__(self):
        # Keywords that indicate official data is needed
        self.official_keywords = [
            "regulation", "law", "act", "policy", "guideline", "official",
            "government", "statistics", "census", "tax", "sebi", "rbi",
            "fda", "who", "ministry", "department", "scheme", "compliance"
        ]

        # Common official domains to enforce
        self.official_domains = [
            "gov", "nic.in", "gov.in", "who.int", "rbi.org.in", "sebi.gov.in"
        ]

    def needs_official_sources(self, query: str) -> bool:
        """Determines if the query implies a need for official sources."""
        cleaned = query.lower()
        for kw in self.official_keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', cleaned):
                return True
        return False

    def enhance_search_queries(self, queries: List[str]) -> List[str]:
        """
        Enhances a list of search queries. If the original query needs official sources,
        appends domain-restricted queries to the list.
        """
        enhanced_queries = []
        for q in queries:
            enhanced_queries.append(q)
            if self.needs_official_sources(q):
                # Generate a strict query targeting official domains
                domains_str = " OR ".join([f"site:{d}" for d in self.official_domains])
                enhanced_q = f"{q} ({domains_str})"
                enhanced_queries.append(enhanced_q)
                logger.debug(f"Added official source restricted query: {enhanced_q}")
                
        # Deduplicate while preserving order
        seen = set()
        result = []
        for eq in enhanced_queries:
            if eq not in seen:
                seen.add(eq)
                result.append(eq)
                
        return result
