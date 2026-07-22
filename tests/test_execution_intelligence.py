import pytest
import time
from unittest.mock import MagicMock, patch

from deployment.runtime.query_classifier import QueryClassifier
from deployment.runtime.retrieval.retriever import Retriever
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_strategy import ResearchStrategy
from deployment.runtime.models.retrieval_result import CandidateSource, RetrievalResult

def test_query_complexity_scoring():
    classifier = QueryClassifier()
    # Simple query
    score1 = classifier.calculate_complexity("who is the CEO of Apple?")
    # Complex query
    score2 = classifier.calculate_complexity("analyze the revenue growth of Apple vs Microsoft between 2020 and 2023 and explain the implications on stock prices")
    
    assert score1 < score2
    assert score2 >= 50

def test_deterministic_extraction():
    # Setup Strategy & ToolRegistry
    strategy = ResearchStrategy(strategy_name="LOOKUP", intent="FACT_LOOKUP")
    registry = MagicMock()
    retriever = Retriever(registry, strategy)
    
    snippets = [
        "Some unrelated text here.",
        "Tim Cook is the CEO of Apple.",
        "Another snippet."
    ]
    
    answer = retriever.extract_direct_answer("who is the ceo of apple?", snippets)
    assert answer == "Tim Cook"

def test_consensus_calculation():
    controller = ResearchController(MagicMock(), MagicMock(), MagicMock())
    sources = [
        CandidateSource(url="http://a.com", snippet="The population is 8.5 million.", domain="a.com"),
        CandidateSource(url="http://b.com", snippet="New York population reached 8.5 million.", domain="b.com"),
        CandidateSource(url="http://c.com", snippet="About 8.5 million people live there.", domain="c.com")
    ]
    
    score = controller.calculate_consensus("population of New York", sources)
    # They share the number "8.5", so consensus should be high
    assert score > 15.0

def test_structured_validation_headers():
    from deployment.runtime.advanced_result_builder import AdvancedResultBuilder
    from deployment.runtime.response_planner import ResponsePlan
    
    builder = AdvancedResultBuilder()
    plan = ResponsePlan(output_format="table", target_audience="general", section_count=1)
    
    content = {
        "title": "Test Table",
        "headers": ["| Name |", " Age "],
        "rows": [["Alice", 30], ["Bob", 25, "Extra"]], # Bob has an extra column that should be truncated
        "evidence_ids": ["source_1"]
    }
    
    result = builder.build(plan, content, [])
    assert "Name" in result
    assert "| Name" not in result # The literal pipe was stripped
    assert "source_1" in result
    # Row truncation check - "Extra" should not be included properly or padded
    assert "Extra" not in result

def test_quality_evaluator_scoring():
    from deployment.runtime.intelligence.quality_evaluator import QualityEvaluator
    qe = QualityEvaluator()
    
    # Very good answer
    good_ans = "Here is the direct answer. [1] It is based on this URL: http://test.com"
    scores1 = qe.evaluate("test", good_ans, 1, "LOOKUP", "openai", "gpt-4o")
    
    # Bad answer
    bad_ans = "I don't know."
    scores2 = qe.evaluate("test", bad_ans, 0, "RESEARCH", "openai", "gpt-4o")
    
    assert scores1["overall_score"] > scores2["overall_score"]
    assert scores1["citation_quality"] == 100
    assert scores2["citation_quality"] == 0
