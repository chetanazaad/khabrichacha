import re
from typing import Dict, Any
from deployment.runtime.models.retrieval_result import CandidateSource
from deployment.runtime.models.trust_evaluation import TrustEvaluation

class TrustEvaluator:
    """Evaluates the trustworthiness, quality, bias, and authority of candidate sources."""

    def evaluate(self, source: CandidateSource) -> TrustEvaluation:
        # 1. Authority (inherited from ranker/profiles)
        authority = source.trust_score if source.trust_score > 0 else 50.0

        # 2. Freshness heuristic
        freshness = 50.0
        # If the snippet has relative date terms (e.g. "ago", "today", "yesterday", "recent")
        combined_text = (source.title + " " + source.snippet).lower()
        if any(term in combined_text for term in ["hours ago", "days ago", "yesterday", "today", "updated]):"]):
            freshness = 90.0
        elif any(term in combined_text for term in ["this month", "recent", "weeks ago"]):
            freshness = 75.0

        # 3. Bias heuristic (opinion keywords vs neutral reporting)
        bias_score = 75.0  # default neutral-high
        opinion_cues = ["i think", "in my opinion", "we believe", "should", "must", "devastating", "amazing", "shameful", "worst", "best"]
        opinion_matches = sum(1 for cue in opinion_cues if cue in combined_text)
        if opinion_matches > 0:
            bias_score = max(75.0 - (opinion_matches * 15.0), 20.0)

        # 4. Snippet Quality (length and specificity)
        quality = 50.0
        snippet_len = len(source.snippet)
        if snippet_len > 150:
            quality = 85.0
        elif snippet_len > 70:
            quality = 70.0
        else:
            quality = 40.0

        # If numbers/statistics are present in the snippet, add a specificity bonus
        if re.search(r'\b\d+(?:\.\d+)?%|\b\$\d+|\b\d{4}\b', source.snippet):
            quality = min(quality + 10.0, 100.0)

        # 5. Citations heuristic (presence of referencing terms like "according to", "reported by", "published in")
        citations = 50.0
        citation_cues = ["according to", "reported by", "published", "cited", "source", "study by"]
        if any(cue in combined_text for cue in citation_cues):
            citations = 80.0

        # 6. Overall Weighted Trust Score
        # Authority: 40%, Quality: 20%, Citations: 15%, Bias: 15%, Freshness: 10%
        overall_score = (
            (0.40 * authority) +
            (0.20 * quality) +
            (0.15 * citations) +
            (0.15 * bias_score) +
            (0.10 * freshness)
        )

        # Explanation logic
        reason = f"Domain category '{source.domain_category}' has default authority {authority:.0f}."
        if bias_score < 50.0:
            reason += " Snippet shows potential subjective or opinionated language."
        if quality > 80.0:
            reason += " Source snippet is descriptive and contains specific terms/numbers."
        if citations > 70.0:
            reason += " Source references other studies or reports."

        return TrustEvaluation(
            authority=authority,
            freshness=freshness,
            bias=bias_score,
            quality=quality,
            citations=citations,
            overall_score=overall_score,
            reason=reason
        )
