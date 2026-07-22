import os
import re
import yaml
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from loguru import logger

class SourceRanker:
    """Ranks search results based on authority, domain types, freshness, and relevance."""

    def __init__(self, profiles_path: Optional[str] = None):
        if not profiles_path:
            profiles_path = os.path.join(
                os.path.dirname(__file__),
                "domain_profiles.yaml"
            )
            if not os.path.exists(profiles_path):
                profiles_path = os.path.join("deployment", "runtime", "retrieval", "domain_profiles.yaml")
                
        self.profiles_path = profiles_path
        self.profiles = self._load_profiles()

    def _load_profiles(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.profiles_path):
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    return data.get("profiles", {})
            else:
                logger.warning(f"Profiles not found at {self.profiles_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            return {}

    def get_domain_category(self, url: str) -> str:
        """Determines the domain category (e.g., gov, edu, news) based on the URL."""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
        except Exception:
            return "general"

        for cat_name, profile in self.profiles.items():
            patterns = profile.get("patterns", [])
            # Check suffix (for .gov, .edu etc) or substring
            for pattern in patterns:
                if pattern.startswith("."):
                    if netloc.endswith(pattern):
                        return cat_name
                else:
                    if pattern in netloc:
                        return cat_name
                        
        # Default heuristics if no pattern matches
        if ".gov" in netloc or ".nic.in" in netloc:
            return "gov"
        if ".edu" in netloc or ".ac." in netloc:
            return "edu"
            
        return "general"

    def detect_source_type(self, category: str, url: str) -> str:
        if category == "gov":
            return "Government"
        elif category in ["edu", "research"]:
            return "Academic"
        elif category == "wikipedia":
            return "Wikipedia"
        elif category == "news":
            return "News"
        elif category == "blogs":
            return "Blog"
        elif category == "forums":
            return "Forum"
        elif category == "social":
            return "Social Media"
        elif category == "company":
            if "docs" in url or "documentation" in url or "developer" in url:
                return "Documentation"
            return "Official"
        return "Unknown"

    def rank(self, results: List[Dict[str, Any]], query: str, intent: str = "General Research") -> List[Dict[str, Any]]:
        """
        Ranks search results using a multi-factor weighted scoring system, adapted to intent.
        """
        ranked_results = []
        query_words = set(query.lower().split())

        for idx, r in enumerate(results):
            url = r.get("url", "")
            title = r.get("title", "")
            snippet = r.get("snippet", "")

            # Determine category and clean source type
            category = self.get_domain_category(url)
            source_type = self.detect_source_type(category, url)
            profile = self.profiles.get(category, {})

            # 1. Authority Score (domain authority from profile)
            authority = profile.get("authority", 50.0)

            # 2. Domain Trust Score (domain trust from profile)
            domain_trust = profile.get("trust", 50.0)

            # Boost weights according to intent
            if intent in ["Financial", "Statistical", "Regulation"]:
                if category == "gov":
                    authority = min(100.0, authority + 15.0)
                    domain_trust = min(100.0, domain_trust + 15.0)
                elif category == "research":
                    authority = min(100.0, authority + 10.0)
            elif intent in ["Person", "Country", "Organization"]:
                if category == "wikipedia":
                    authority = min(100.0, authority + 20.0)
                    domain_trust = min(100.0, domain_trust + 20.0)
            elif intent in ["Scientific", "Academic"]:
                if category in ["edu", "research"]:
                    authority = min(100.0, authority + 15.0)
                    domain_trust = min(100.0, domain_trust + 15.0)

            # 3. Freshness Score (heuristic based on date cues in URL/snippet)
            freshness = 50.0  # Default neutral
            year_matches = re.findall(r'\b(202[0-9])\b', url + " " + snippet)
            if year_matches:
                latest_year = max(int(y) for y in year_matches)
                if latest_year >= 2025:
                    freshness = 90.0
                elif latest_year == 2024:
                    freshness = 75.0
                else:
                    freshness = 60.0
            
            if intent == "News":
                freshness = min(100.0, freshness + 15.0)

            # 4. Popularity Score (rank in search engine results - higher ranks get slight bonus)
            popularity = max(100.0 - (idx * 5.0), 30.0)

            # 5. Language/Keyword Match Score (overlap of query words in title/snippet)
            combined_text = (title + " " + snippet).lower()
            matching_words = sum(1 for w in query_words if w in combined_text)
            language_match = (matching_words / len(query_words) * 100.0) if query_words else 50.0

            # 6. Document Type/Other heuristics (PDF bias if requested, etc.)
            other_score = 50.0
            if url.endswith(".pdf"):
                other_score = 80.0
                if intent in ["Financial", "Statistical", "Scientific"]:
                    other_score = 95.0

            # Overall Score calculation
            score = (
                (0.30 * authority) +
                (0.20 * freshness) +
                (0.20 * domain_trust) +
                (0.15 * popularity) +
                (0.10 * language_match) +
                (0.05 * other_score)
            )

            # 7. Quality score breakdown
            completeness = min(100.0, len(snippet) / 2.0)
            duplicates_penalty = 20.0 if r.get("is_duplicate", False) else 0.0
            final_quality_score = max(0.0, score - duplicates_penalty)

            # Create candidate source copy
            r_copy = r.copy()
            r_copy["rank_score"] = final_quality_score
            r_copy["trust_score"] = domain_trust
            r_copy["domain_category"] = category
            r_copy["source_type"] = source_type
            r_copy["quality_score_breakdown"] = {
                "Trust": domain_trust,
                "Freshness": freshness,
                "Completeness": completeness,
                "Relevance": language_match,
                "Authority": authority,
                "Duplicates": duplicates_penalty,
                "Final": final_quality_score
            }
            ranked_results.append(r_copy)

        # Sort descending by rank_score
        ranked_results.sort(key=lambda x: x.get("rank_score", 0.0), reverse=True)
        return ranked_results
