from typing import List, Dict, Any
from deployment.runtime.models.knowledge_objects import Entity, Claim, Relation

class KnowledgeGraph:
    """Lightweight in-memory knowledge graph representing entities, claims, evidence, and relationships."""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.claims: List[Claim] = []
        self.relations: List[Relation] = []

    def add_entity(self, entity: Entity) -> None:
        """Adds or merges an entity in the graph."""
        name = entity.normalized_name.lower()
        if name not in self.entities:
            self.entities[name] = entity
        else:
            # Merge aliases
            existing = self.entities[name]
            merged_aliases = list(set(existing.aliases + entity.aliases))
            existing.aliases = merged_aliases

    def add_claim(self, claim: Claim) -> None:
        """Adds a factual claim to the graph."""
        self.claims.append(claim)

    def add_relation(self, relation: Relation) -> None:
        """Adds a relationship edge between entities."""
        self.relations.append(relation)

    def get_timeline(self, entity_name: str) -> List[Dict[str, Any]]:
        """Extracts chronological milestones related to the entity."""
        timeline = []
        entity_name_lower = entity_name.lower()
        
        # Scrape claims for date cues
        import re
        for claim in self.claims:
            if entity_name_lower in claim.statement.lower():
                # Try to find year
                year_match = re.search(r'\b(20\d{2})\b', claim.statement)
                if year_match:
                    timeline.append({
                        "year": int(year_match.group(1)),
                        "event": claim.statement,
                        "source": claim.source_url
                    })
                    
        timeline.sort(key=lambda x: x["year"])
        return timeline

    def find_contradictions(self) -> List[Dict[str, Any]]:
        """Identifies conflicting claims or relations in the graph."""
        contradictions = []
        # Basic contradiction checking: look for numeric discrepancies in similar claims
        # e.g., claims on same subject with different numbers
        import re
        
        for i in range(len(self.claims)):
            for j in range(i + 1, len(self.claims)):
                c1 = self.claims[i]
                c2 = self.claims[j]
                
                # Check if claims reference same subject (e.g. GDP of India)
                # Parse numeric values
                nums1 = re.findall(r'\b\d+(?:\.\d+)?\b', c1.statement)
                nums2 = re.findall(r'\b\d+(?:\.\d+)?\b', c2.statement)
                
                if nums1 and nums2:
                    # Find overlap of nouns/words to see if they are talking about the same thing
                    words1 = set(c1.statement.lower().split())
                    words2 = set(c2.statement.lower().split())
                    overlap = words1.intersection(words2)
                    
                    # If high word overlap and different numeric values, flag contradiction
                    if len(overlap) >= 5 and nums1[0] != nums2[0]:
                        contradictions.append({
                            "subject": " ".join(list(overlap)[:3]),
                            "claim_1": c1.statement,
                            "source_1": c1.source_url,
                            "claim_2": c2.statement,
                            "source_2": c2.source_url,
                            "discrepancy": f"Claim 1 has {nums1[0]}, Claim 2 has {nums2[0]}."
                        })
                        
        return contradictions

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the knowledge graph structure to a dictionary."""
        return {
            "entities": [e.model_dump() for e in self.entities.values()],
            "claims": [c.model_dump() for c in self.claims],
            "relations": [r.model_dump() for r in self.relations]
        }
