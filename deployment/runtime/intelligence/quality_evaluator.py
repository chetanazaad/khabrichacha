import re
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
            "hallucination_risk": "High",
            # Was populated by honestly checking whether the LLM self-grade
            # step actually produced parseable numbers ("llm_graded") or had
            # to fall back to a default because the model's response
            # couldn't be parsed/failed to generate at all
            # ("fallback_default") -- this used to be indistinguishable
            # from the outside, so a flaky small model silently defaulting
            # every time looked identical to a real, considered grade.
            "grading_method": "not_run",
        }
        
        # 1. Basic heuristics
        heuristic_relevance = 0
        if source_count > 0:
            heuristic_relevance = 20
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
        llm_relevance = None
        try:
            session = Session()
            llm_manager = LLMManager(session.config)
            provider_obj = llm_manager.get_provider(provider)
            
            prompt = (
                f"You are a quality grader. Rate the following answer to the query '{query}' "
                f"on a scale of 0 to 100 for Completeness and Relevance.\n\n"
                f"Answer: {answer[:1000]}...\n\n"
                f"Respond with ONLY two numbers separated by a comma, like this: 75, 82\n"
                f"Do not add any other words, explanation, or punctuation."
            )
            llm_response = provider_obj.generate(prompt)

            # Robust parsing: small/local models very often ignore "only
            # output two numbers" and add preamble/explanation/markdown
            # anyway. Rather than requiring an exact "N, M" format (which
            # silently and unpredictably falls back to defaults whenever a
            # model adds so much as one stray word), pull out the first two
            # 0-100 integers found anywhere in the response.
            found_numbers = [int(n) for n in re.findall(r"\b(\d{1,3})\b", llm_response)]
            found_numbers = [n for n in found_numbers if 0 <= n <= 100]

            if len(found_numbers) >= 2:
                scores["completeness"] = found_numbers[0]
                llm_relevance = found_numbers[1]
                scores["grading_method"] = "llm_graded"
            else:
                raise ValueError(
                    f"Could not find two 0-100 numbers in grader response: {llm_response[:200]!r}"
                )
        except Exception as e:
            logger.warning(f"QualityEvaluator LLM grading failed or was unparseable: {e}")
            # A neutral, middling default rather than a generous 80 -- an
            # overly generous silent default was masking exactly the cases
            # where grading wasn't actually happening, which produced
            # unpredictable escalation behavior that looked identical to a
            # real (confident) grade from the outside.
            scores["completeness"] = 60
            llm_relevance = 60
            scores["grading_method"] = "fallback_default"

        # Combine the heuristic relevance signal (based on whether any
        # sources were actually found) with the self-graded relevance
        # score, instead of letting the self-grade silently overwrite and
        # discard the heuristic signal entirely, which is what happened
        # before regardless of whether grading succeeded or failed.
        scores["relevance"] = min(100, round((heuristic_relevance * 2 + llm_relevance) / 2))
            
        overall_score = (scores["completeness"] + scores["correctness"] + scores["relevance"] + scores["structure"] + scores["citation_quality"]) / 5.0
        scores["overall_score"] = min(100.0, max(0.0, overall_score))
            
        return scores
