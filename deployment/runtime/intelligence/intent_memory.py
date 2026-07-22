from typing import List, Dict, Any, Optional
from loguru import logger
import re

class IntentMemory:
    """
    Tracks and extracts persistent user constraints across a research session.
    """
    
    def __init__(self):
        self.constraints: List[str] = []
        
        # Keywords that indicate a constraint rather than a topic
        self.constraint_keywords = [
            r"only (use|from|show)",
            r"(must|should) be",
            r"ignore",
            r"exclude",
            r"don'?t use",
            r"format as",
            r"keep it (short|brief|detailed)",
            r"focus on"
        ]

    def add_query(self, query: str):
        """Extracts constraints from a new query and adds them to memory."""
        query_lower = query.lower()
        extracted = []
        
        for kw in self.constraint_keywords:
            if re.search(kw, query_lower):
                # We store the whole query or just the phrase for now
                # A more advanced version would use an LLM to parse the exact constraint
                extracted.append(query)
                break
                
        if extracted:
            for ext in extracted:
                if ext not in self.constraints:
                    self.constraints.append(ext)
                    logger.debug(f"Stored user constraint: {ext}")

    def get_active_constraints(self) -> List[str]:
        """Returns the list of active constraints."""
        return self.constraints
        
    def format_for_prompt(self) -> str:
        """Formats the constraints for injection into an LLM prompt."""
        if not self.constraints:
            return ""
            
        res = "Please adhere to the following user constraints from previous interactions:\n"
        for c in self.constraints:
            res += f"- {c}\n"
        return res
