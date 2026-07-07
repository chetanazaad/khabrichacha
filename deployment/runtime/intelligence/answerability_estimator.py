import re
from typing import Optional
from loguru import logger

class AnswerabilityEstimator:
    """
    Estimates whether a query can be answered directly using internal knowledge 
    or basic logic, bypassing the need for web search.
    """

    def __init__(self):
        # Patterns that strongly indicate a question doesn't need search
        self.fast_patterns = [
            # Math
            r"^\s*[\d\.\+\-\*\/\(\)\^\s]+(?:=|\?)?\s*$",
            r"^(calculate|compute|what is)\s+[\d\.\+\-\*\/\(\)\^\s]+",
            # Simple factual definitions
            r"^(what is|define|what are)\s+[a-zA-Z\s\-]+$",
            # Translation
            r"^(translate|how to say)\s+.+\s+(in|to)\s+[a-zA-Z]+$",
            # Code syntax questions
            r"^(how to|write a|show me)\s+(python|javascript|java|c\+\+|go|rust|sql)\s+(script|code|function|class|loop|query)\s+to\s+.+",
            # Basic conversions
            r"^(convert|what is)\s+\d+\s*[a-zA-Z]+\s+(in|to)\s+[a-zA-Z]+$"
        ]

        # Keywords that strongly indicate search IS needed
        self.requires_search_keywords = [
            "latest", "recent", "news", "today", "yesterday", "tomorrow",
            "stock price", "current", "upcoming", "happening", "live", "weather",
            "who won", "score", "update", "newest"
        ]

    def can_answer_directly(self, query: str) -> bool:
        """
        Returns True if the query can likely be answered without web search.
        """
        cleaned_query = query.strip().lower()

        # 1. Check if it explicitly needs current information
        for kw in self.requires_search_keywords:
            if kw in cleaned_query:
                logger.debug(f"Query requires search due to temporal keyword: {kw}")
                return False

        # 2. Check against fast answerable patterns
        for pattern in self.fast_patterns:
            if re.match(pattern, cleaned_query):
                logger.debug(f"Query matches fast answer pattern: {pattern}")
                return True

        return False
