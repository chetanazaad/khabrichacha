from typing import Dict, List, Any
from pydantic import BaseModel, Field

class AggregatedConfidence(BaseModel):
    overall: float = 0.0              # 0.0 to 100.0
    contributors: Dict[str, float] = Field(default_factory=dict)
    weaknesses: List[str] = Field(default_factory=list)
    explanation: str = ""

class ConfidenceAggregator:
    """Aggregates confidence scores from all processing phases to output an overall rating."""

    def aggregate(
        self,
        retrieval_conf: float = 1.0,      # 0.0 to 1.0
        ranking_conf: float = 1.0,        # 0.0 to 1.0
        trust_conf: float = 1.0,          # 0.0 to 1.0
        consensus_conf: float = -1.0,     # 0.0 to 1.0 (-1.0 means N/A)
        extraction_conf: float = -1.0,    # 0.0 to 1.0
        reasoning_conf: float = 1.0       # 0.0 to 1.0
    ) -> AggregatedConfidence:
        contributors = {
            "retrieval": retrieval_conf,
            "ranking": ranking_conf,
            "trust": trust_conf,
            "reasoning": reasoning_conf
        }

        # Weighted calculation
        # Base: Retrieval (15%), Ranking (15%), Trust (30%), Reasoning (40%)
        weights = {
            "retrieval": 0.15,
            "ranking": 0.15,
            "trust": 0.30,
            "reasoning": 0.40
        }

        if consensus_conf >= 0.0:
            contributors["consensus"] = consensus_conf
            # Adjust weights: Retrieval (10%), Ranking (10%), Trust (20%), Consensus (30%), Reasoning (30%)
            weights = {
                "retrieval": 0.10,
                "ranking": 0.10,
                "trust": 0.20,
                "consensus": 0.30,
                "reasoning": 0.30
            }

        if extraction_conf >= 0.0:
            contributors["extraction"] = extraction_conf
            # Adjust weights if extraction is active
            if "consensus" in contributors:
                weights = {
                    "retrieval": 0.08,
                    "ranking": 0.08,
                    "trust": 0.14,
                    "extraction": 0.20,
                    "consensus": 0.25,
                    "reasoning": 0.25
                }
            else:
                weights = {
                    "retrieval": 0.10,
                    "ranking": 0.10,
                    "trust": 0.20,
                    "extraction": 0.25,
                    "reasoning": 0.35
                }

        # Calculate overall score
        overall_fraction = 0.0
        for key, val in contributors.items():
            overall_fraction += val * weights.get(key, 0.0)

        overall_score = overall_fraction * 100.0
        
        # Identify weaknesses
        weaknesses = []
        if retrieval_conf < 0.60:
            weaknesses.append("Low search result density or high local mismatch.")
        if trust_conf < 0.60:
            weaknesses.append("Sources are mostly low-authority domains (blogs/social platforms).")
        if consensus_conf >= 0.0 and consensus_conf < 0.60:
            weaknesses.append("Conflicting numbers or data values found across sources.")
        if reasoning_conf < 0.60:
            weaknesses.append("LLM reasoning reported low confidence or high ambiguity.")

        # Explanation
        explanation = f"Confidence score of {overall_score:.0f}/100 is supported by "
        high_con_keys = [k for k, v in contributors.items() if v >= 0.80]
        if high_con_keys:
            explanation += f"strong {', '.join(high_con_keys)} performance. "
        else:
            explanation += "moderate performance across most stages. "

        if weaknesses:
            explanation += f"Key limitations: {'; '.join(weaknesses)}"
        else:
            explanation += "No significant reliability limitations detected."

        return AggregatedConfidence(
            overall=round(overall_score, 1),
            contributors=contributors,
            weaknesses=weaknesses,
            explanation=explanation
        )
