import re
from typing import List, Dict, Any, Tuple
from loguru import logger
from deployment.runtime.models.consensus_result import ConsensusResult

class ConsensusEngine:
    """Verifies factual and numerical data points across multiple sources to establish consensus."""

    def verify_numerical(self, claim: str, source_values: List[Dict[str, Any]]) -> ConsensusResult:
        """
        Verifies numerical values (e.g., population, GDP, budget) collected from multiple sources.
        Each item in source_values should be: {"source_name": str, "value": float, "weight": float}
        """
        if not source_values:
            return ConsensusResult(claim=claim, resolution="unresolved", confidence=0.0)

        # Sort values
        values = [item.get("value") for item in source_values if item.get("value") is not None]
        if not values:
            return ConsensusResult(claim=claim, resolution="unresolved", confidence=0.0)

        # Count frequencies
        from collections import Counter
        freq = Counter(values)
        majority_val, majority_count = freq.most_common(1)[0]
        majority_pct = (majority_count / len(values)) * 100.0

        # Calculate weighted average
        total_weight = sum(item.get("weight", 1.0) for item in source_values)
        if total_weight > 0:
            weighted_sum = sum(item.get("value", 0.0) * item.get("weight", 1.0) for item in source_values)
            weighted_avg = weighted_sum / total_weight
        else:
            weighted_avg = sum(values) / len(values)

        agreeing_sources = []
        conflicting_sources = []
        conflicts = []

        # Threshold for numeric conflict (e.g. > 5% difference)
        for item in source_values:
            val = item.get("value")
            source_name = item.get("source_name", "Unknown Source")
            
            # If value matches the majority
            if val == majority_val:
                agreeing_sources.append(source_name)
            else:
                conflicting_sources.append(source_name)
                conflicts.append({
                    "source": source_name,
                    "value": val,
                    "difference": abs(val - majority_val)
                })

        # Resolution strategy
        resolution = "unresolved"
        resolved_val = None
        confidence = 0.0

        if majority_pct >= 60.0:
            resolution = "majority"
            resolved_val = majority_val
            confidence = min(majority_pct / 100.0, 0.95)
        else:
            # Check if values are close enough to average (within 2%)
            spread = max(values) - min(values)
            avg = sum(values) / len(values)
            if avg > 0 and (spread / avg) <= 0.05:
                resolution = "weighted_average"
                resolved_val = round(weighted_avg, 2)
                confidence = 0.80
            else:
                resolution = "unresolved"
                resolved_val = majority_val  # Fallback to majority
                confidence = 0.40

        return ConsensusResult(
            claim=claim,
            agreement_percentage=majority_pct,
            agreeing_sources=agreeing_sources,
            conflicting_sources=conflicting_sources,
            weighted_value=resolved_val,
            confidence=confidence,
            conflicts=conflicts,
            resolution=resolution
        )

    def extract_and_verify(self, claim: str, docs: List[Dict[str, Any]], regex_pattern: str) -> ConsensusResult:
        """
        Helper method to extract numerical values from snippets using a regex pattern
        and then verify them.
        """
        source_values = []
        
        for doc in docs:
            snippet = doc.get("snippet", "") or doc.get("content", "")
            url = doc.get("url", "")
            trust = doc.get("trust_score", 50.0) / 100.0 # Weight is proportional to trust
            
            match = re.search(regex_pattern, snippet)
            if match:
                try:
                    # Clean commas, dollar signs
                    val_str = match.group(1).replace(",", "").replace("$", "").strip()
                    val = float(val_str)
                    source_values.append({
                        "source_name": url,
                        "value": val,
                        "weight": trust
                    })
                except Exception:
                    pass

        return self.verify_numerical(claim, source_values)
