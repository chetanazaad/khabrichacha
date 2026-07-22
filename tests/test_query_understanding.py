from deployment.runtime.query_understanding import QueryUnderstandingEngine


def test_understanding_detects_count_and_comparison():
    engine = QueryUnderstandingEngine()
    count_result = engine.understand("How many times has India won the Cricket World Cup?")
    comparison_result = engine.understand("Compare GPT-5 and Gemini")

    assert count_result.answer_type == "count"
    assert comparison_result.answer_type == "comparison"
    assert count_result.strategy_hint == "STRUCTURED"
    assert comparison_result.strategy_hint == "COMPARISON"
