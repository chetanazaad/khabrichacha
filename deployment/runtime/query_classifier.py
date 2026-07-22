import os
import re
import yaml
from typing import Dict, Any, Optional, List
from loguru import logger
from deployment.runtime.models.research_strategy import ResearchStrategy, ExecutionBudget
from deployment.runtime.query_understanding import QueryUnderstandingEngine

class QueryClassifier:
    """Intelligently classifies research queries and routes them to appropriate execution strategies."""

    def __init__(self, rules_path: Optional[str] = None):
        if not rules_path:
            rules_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "runtime",
                "strategy_rules.yaml"
            )
            # Fallback if __file__ path is complex
            if not os.path.exists(rules_path):
                rules_path = os.path.join("deployment", "runtime", "strategy_rules.yaml")

        self.rules_path = rules_path
        self.rules = self._load_rules()
        self.understanding_engine = QueryUnderstandingEngine()

    def _load_rules(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.rules_path):
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Rules file not found at {self.rules_path}. Using empty rules.")
                return {}
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            return {}

    def calculate_complexity(self, query: str) -> int:
        """
        Calculates a complexity score (0-100) based on query characteristics:
        entities, temporal constraints, comparison operators, and reasoning depth.
        """
        score = 0
        q_lower = query.lower()
        
        # 1. Comparison & Multiple entities
        if " vs " in q_lower or " versus " in q_lower:
            score += 20
        if " and " in q_lower or " or " in q_lower:
            score += 5
            
        # 2. Temporal constraints
        if re.search(r'\b(20\d{2}|19\d{2})\b', q_lower):
            score += 15
        if re.search(r'\b(before|after|during|since|until)\b', q_lower):
            score += 10
            
        # 3. Numeric demands & structured
        if re.search(r'\b(how many|how much|statistics|data|table|list)\b', q_lower):
            score += 15
            
        # 4. Expected reasoning depth
        if re.search(r'\b(why|how|analyze|evaluate|explain|implications|impact)\b', q_lower):
            score += 30
        if re.search(r'\b(research|deep dive|comprehensive)\b', q_lower):
            score += 40
            
        # 5. Ambiguity / length
        word_count = len(q_lower.split())
        if word_count > 15:
            score += 10
        elif word_count < 5:
            # Simple lookups typically have fewer words
            score += 5
            
        return min(100, max(0, score))

    def classify(self, mission: str, strategy_override: Optional[str] = None) -> ResearchStrategy:
        """
        Classifies the mission into a ResearchStrategy.
        If strategy_override is specified and not 'auto' or None, bypasses classification.
        """
        complexity_score = self.calculate_complexity(mission)
        understanding = self.understanding_engine.understand(mission)

        # Lowercase strategy override check
        if strategy_override:
            strategy_override_clean = strategy_override.strip().upper()
            if strategy_override_clean != "AUTO" and strategy_override_clean in self.rules.get("strategies", {}):
                logger.info(f"Applying manual strategy override: {strategy_override_clean} (Complexity: {complexity_score})")
                return self._build_strategy(strategy_override_clean, mission, confidence=1.0, complexity=complexity_score)

        cleaned_mission = mission.strip().lower()

        if re.match(r"^[\d\s\+\-\*\/\.\(\)]+$", cleaned_mission):
            return self._build_strategy("FAST", mission, confidence=0.99, intent="MATHEMATICS")

        if understanding.strategy_hint and cleaned_mission:
            strategy_override_clean = understanding.strategy_hint.upper()
            if strategy_override_clean in self.rules.get("strategies", {}) and strategy_override_clean in {"COMPARISON", "ANALYSIS", "RESEARCH", "DEEP_RESEARCH", "STRUCTURED"}:
                return self._build_strategy(strategy_override_clean, mission, confidence=max(0.65, understanding.confidence), complexity=complexity_score, intent=understanding.answer_type.upper())
        classification_rules = self.rules.get("classification", {})
        
        # Tier 1: Regex & Key Prefix matches (FAST / LOOKUP)
        
        # Math match
        math_pattern = classification_rules.get("fast_patterns", {}).get("math")
        if math_pattern and re.match(math_pattern, cleaned_mission):
            return self._build_strategy("FAST", mission, confidence=0.99, intent="MATHEMATICS")

        # Fact prefixes
        fact_prefixes = classification_rules.get("fast_patterns", {}).get("fact_prefixes", [])
        for prefix in fact_prefixes:
            if cleaned_mission.startswith(prefix.lower()):
                return self._build_strategy("FAST", mission, confidence=0.95, intent="FACT_LOOKUP", complexity=complexity_score)

        # Programming syntax
        programming_keywords = classification_rules.get("fast_patterns", {}).get("programming", [])
        for keyword in programming_keywords:
            if keyword.lower() in cleaned_mission:
                return self._build_strategy("FAST", mission, confidence=0.95, intent="PROGRAMMING_SYNTAX", complexity=complexity_score)

        # Lookup keywords
        lookup_keywords = classification_rules.get("lookup_keywords", [])
        for keyword in lookup_keywords:
            if keyword.lower() in cleaned_mission:
                return self._build_strategy("LOOKUP", mission, confidence=0.90, intent="NEWS_OR_LOOKUP", complexity=complexity_score)

        # Tier 2: Keyword scoring matrices
        scores = {
            "STRUCTURED": 0.0,
            "COMPARISON": 0.0,
            "ANALYSIS": 0.0,
            "RESEARCH": 0.0,
            "DEEP_RESEARCH": 0.0
        }

        # Structured keywords
        for kw in classification_rules.get("structured_keywords", []):
            if kw.lower() in cleaned_mission:
                scores["STRUCTURED"] += 1.0

        # Comparison keywords/patterns
        for pattern in classification_rules.get("comparison_patterns", []):
            if pattern.lower() in cleaned_mission:
                scores["COMPARISON"] += 1.5

        # Analysis keywords
        for kw in classification_rules.get("analysis_keywords", []):
            if kw.lower() in cleaned_mission:
                scores["ANALYSIS"] += 1.0

        # Research keywords
        for kw in classification_rules.get("research_keywords", []):
            if kw.lower() in cleaned_mission:
                scores["RESEARCH"] += 1.0

        # Deep Research keywords
        for kw in classification_rules.get("deep_research_keywords", []):
            if kw.lower() in cleaned_mission:
                scores["DEEP_RESEARCH"] += 1.5

        # Find the highest scoring strategy
        best_strategy = "LOOKUP"  # Default
        best_score = 0.0
        for strategy, score in scores.items():
            if score > best_score:
                best_score = score
                best_strategy = strategy

        # Tier 3: Fallback heuristics (if scores are 0 or query is complex)
        words = cleaned_mission.split()
        word_count = len(words)
        
        if best_score == 0.0:
            if word_count < 8:
                best_strategy = "LOOKUP"
                best_score = 0.70
            elif word_count <= 20:
                best_strategy = "ANALYSIS"
                best_score = 0.75
            else:
                best_strategy = "RESEARCH"
                best_score = 0.80

        # Calculate confidence base
        confidence = min(0.5 + (best_score * 0.15), 0.95)

        final_strategy = best_strategy
        return self._build_strategy(final_strategy, mission, confidence=confidence, complexity=complexity_score)

    def understand_query(self, mission: str) -> Dict[str, Any]:
        understanding = self.understanding_engine.understand(mission)
        return understanding.to_dict()

    def _build_strategy(self, name: str, mission: str, confidence: float = 1.0, intent: str = "AUTO_DETECTED", complexity: int = 1) -> ResearchStrategy:
        strategy_config = self.rules.get("strategies", {}).get(name, {})
        if not strategy_config:
            # Fallback hardcoded defaults if rules load failed
            logger.warning(f"Strategy config {name} not found in rules. Using hardcoded defaults.")
            return ResearchStrategy(
                strategy_name=name,
                intent=intent,
                complexity=complexity,
                confidence=confidence,
                requires_planner=(name in ["RESEARCH", "DEEP_RESEARCH"]),
                requires_llm=(name != "LOOKUP" and name != "STRUCTURED"),
                requires_search=(name != "FAST")
            )

        budget_config = strategy_config.get("budget", {})
        budget = ExecutionBudget(
            max_searches=budget_config.get("max_searches", 5),
            max_fetches=budget_config.get("max_fetches", 5),
            max_llm_calls=budget_config.get("max_llm_calls", 3),
            max_iterations=budget_config.get("max_iterations", 5),
            max_runtime_seconds=budget_config.get("max_runtime_seconds", 300)
        )

        return ResearchStrategy(
            strategy_name=name,
            intent=strategy_config.get("intent", intent),
            complexity=complexity,
            confidence=confidence,
            requires_planner=strategy_config.get("requires_planner", False),
            requires_llm=strategy_config.get("requires_llm", True),
            requires_search=strategy_config.get("requires_search", True),
            requires_fetch=strategy_config.get("requires_fetch", True),
            requires_pdf=strategy_config.get("requires_pdf", False),
            requires_reasoning=strategy_config.get("requires_reasoning", name in ["FAST", "COMPARISON", "ANALYSIS", "RESEARCH", "DEEP_RESEARCH"]),
            requires_adaptive_loop=strategy_config.get("requires_adaptive_loop", False),
            requires_evidence_evaluation=strategy_config.get("requires_evidence_evaluation", False),
            requires_report_generation=strategy_config.get("requires_report_generation", False),
            requires_summary=strategy_config.get("requires_summary", False),
            requires_structured_output=strategy_config.get("requires_structured_output", False),
            allow_project_creation=strategy_config.get("allow_project_creation", True),
            allow_workspace_save=strategy_config.get("allow_workspace_save", True),
            preferred_output=strategy_config.get("preferred_output", "direct_answer"),
            max_iterations=strategy_config.get("max_iterations", 5),
            enabled_tools=strategy_config.get("enabled_tools", []),
            execution_budget=budget,
            estimated_latency_seconds=strategy_config.get("estimated_latency_seconds", 10.0),
            estimated_cost=strategy_config.get("estimated_cost", "low")
        )
