from typing import Dict, Any, List
from loguru import logger

from khabrichacha.core.session import Session
from khabrichacha.llm.manager import LLMManager

class QualityEvaluator:
    """
    Evaluates final answer quality across multiple dimensions:
    completeness, correctness, citation quality, structure, relevance, and hallucination risk.
    """
    
    def __init__(self):
        pass

    def evaluate(self, query: str, answer: str, source_count: int, strategy: str, provider: str, model: str) -> Dict[str, Any]:
        """
        Runs a heuristic + fast LLM evaluation on the answer quality.
        """
        scores = {
            "completeness": 0,
            "correctness": 0,
            "citation_quality": 0,
            "structure": 0,
            "relevance": 0,
            "hallucination_risk": "High"
        }
        
        # 1. Basic heuristics
        if source_count > 0:
            scores["relevance"] += 20
            scores["correctness"] += 20
            
        if "http" in answer or "[1]" in answer or "Source" in answer:
            scores["citation_quality"] = 100
            scores["hallucination_risk"] = "Low"
        elif source_count == 0 and strategy not in ["FAST"]:
            scores["hallucination_risk"] = "High"
        else:
            scores["citation_quality"] = 50
            scores["hallucination_risk"] = "Medium"
            
        if "|" in answer and "-" in answer:
            scores["structure"] = 100 # tabular
        elif len(answer.split("\n\n")) > 2:
            scores["structure"] = 80
        else:
            scores["structure"] = 50
            
        # 2. LLM-based Evaluation
        try:
            session = Session()
            llm_manager = LLMManager(session.config)
            provider_obj = llm_manager.get_provider(provider)
            
            prompt = (
                f"You are a quality grader. Rate the following answer to the query '{query}' "
                f"on a scale of 0 to 100 for Completeness and Relevance.\n\n"
                f"Answer: {answer[:1000]}...\n\n"
                f"Output exactly two numbers separated by a comma (Completeness, Relevance)."
            )
            llm_response = provider_obj.generate(prompt)
            parts = llm_response.replace("\n", "").split(",")
            if len(parts) >= 2:
                scores["completeness"] = min(100, max(0, int(parts[0].strip())))
                scores["relevance"] = min(100, max(0, int(parts[1].strip())))
        except Exception as e:
            logger.warning(f"QualityEvaluator LLM grading failed: {e}")
            scores["completeness"] = 80
            scores["relevance"] = 80
            
        overall_score = (scores["completeness"] + scores["correctness"] + scores["relevance"] + scores["structure"] + scores["citation_quality"]) / 5.0
        scores["overall_score"] = min(100.0, max(0.0, overall_score))
            
        return scores
