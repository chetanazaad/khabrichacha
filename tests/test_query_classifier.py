import unittest
from deployment.runtime.query_classifier import QueryClassifier

class TestQueryClassifier(unittest.TestCase):
    def setUp(self):
        self.qc = QueryClassifier()

    def test_fast_strategy(self):
        # Math queries
        self.assertEqual(self.qc.classify("2+2").strategy_name, "FAST")
        self.assertEqual(self.qc.classify(" 10 * 5 + 3 ").strategy_name, "FAST")
        
        # Fact lookups
        self.assertEqual(self.qc.classify("capital of Japan").strategy_name, "FAST")
        self.assertEqual(self.qc.classify("who is the president of the US").strategy_name, "FAST")
        
        # Programming syntax
        self.assertEqual(self.qc.classify("python syntax for loop").strategy_name, "FAST")

    def test_lookup_strategy(self):
        self.assertEqual(self.qc.classify("latest NVIDIA news").strategy_name, "LOOKUP")
        self.assertEqual(self.qc.classify("current CEO of Google").strategy_name, "LOOKUP")
        self.assertEqual(self.qc.classify("weather in Delhi today").strategy_name, "LOOKUP")

    def test_structured_strategy(self):
        self.assertEqual(self.qc.classify("Indian Budget 2020-2025").strategy_name, "STRUCTURED")
        self.assertEqual(self.qc.classify("GDP of India last 10 years").strategy_name, "STRUCTURED")
        self.assertEqual(self.qc.classify("company financials report").strategy_name, "STRUCTURED")

    def test_comparison_strategy(self):
        self.assertEqual(self.qc.classify("GPT-5 vs Gemini comparison").strategy_name, "COMPARISON")
        self.assertEqual(self.qc.classify("difference between Intel and AMD").strategy_name, "COMPARISON")

    def test_analysis_strategy(self):
        self.assertEqual(self.qc.classify("why did NVIDIA stock rise").strategy_name, "ANALYSIS")
        self.assertEqual(self.qc.classify("explain fiscal deficit").strategy_name, "ANALYSIS")

    def test_research_strategy(self):
        self.assertEqual(self.qc.classify("research the history of AI regulation").strategy_name, "RESEARCH")

    def test_deep_research_strategy(self):
        self.assertEqual(self.qc.classify("investigate China semiconductor policy deep dive").strategy_name, "DEEP_RESEARCH")

    def test_manual_override(self):
        # Override FAST to DEEP_RESEARCH
        self.assertEqual(self.qc.classify("2+2", strategy_override="deep_research").strategy_name, "DEEP_RESEARCH")
        # Override lookups to FAST
        self.assertEqual(self.qc.classify("latest NVIDIA news", strategy_override="FAST").strategy_name, "FAST")

if __name__ == "__main__":
    unittest.main()
