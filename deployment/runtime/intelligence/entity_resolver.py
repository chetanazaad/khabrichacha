import re
from typing import List, Dict, Any, Optional
from deployment.runtime.models.knowledge_objects import Entity

class EntityResolver:
    """Resolves and normalizes various aliases, spellings, and abbreviations into a canonical entity."""

    def __init__(self):
        # Local canonical entity mapping database
        self.aliases = {
            "india": ["republic of india", "bharat", "ಭಾರತ", "भारत", "ind"],
            "united states": ["us", "usa", "united states of america", "u.s.a.", "u.s."],
            "united kingdom": ["uk", "u.k.", "britain", "great britain"],
            "narendra modi": ["pm modi", "prime minister narendra modi", "modi", "narendra damodardas modi"],
            "joe biden": ["president biden", "biden", "joseph robinette biden jr"],
            "donald trump": ["trump", "president trump", "donald john trump"],
            "nvidia": ["nvidia corporation", "nvda"],
            "google": ["alphabet", "alphabet inc", "google llc", "googl", "goog"],
            "microsoft": ["microsoft corporation", "msft"]
        }

    def resolve(self, text: str) -> List[Entity]:
        """Scans the text for mentions of known entities and returns them."""
        found_entities = []
        text_lower = text.lower()
        
        for canonical, alias_list in self.aliases.items():
            # Check if canonical itself or any alias is in the text
            matched_alias = None
            if canonical in text_lower:
                matched_alias = canonical
            else:
                for alias in alias_list:
                    # Match word boundary to avoid substrings (like 'us' matching 'status')
                    pattern = r'\b' + re.escape(alias) + r'\b'
                    if re.search(pattern, text_lower):
                        matched_alias = alias
                        break
            
            if matched_alias:
                found_entities.append(Entity(
                    name=matched_alias,
                    normalized_name=canonical,
                    entity_type=self._determine_type(canonical),
                    aliases=alias_list
                ))
                
        return found_entities

    def normalize(self, name: str) -> str:
        """Returns the canonical normalized name for any given alias, or the original if unknown."""
        name_clean = name.strip().lower()
        if name_clean in self.aliases:
            return name_clean
            
        for canonical, alias_list in self.aliases.items():
            if name_clean in alias_list:
                return canonical
        return name

    def _determine_type(self, canonical_name: str) -> str:
        geo = ["india", "united states", "united kingdom"]
        people = ["narendra modi", "joe biden", "donald trump"]
        companies = ["nvidia", "google", "microsoft"]
        
        if canonical_name in geo:
            return "country"
        elif canonical_name in people:
            return "person"
        elif canonical_name in companies:
            return "organization"
        return "concept"
