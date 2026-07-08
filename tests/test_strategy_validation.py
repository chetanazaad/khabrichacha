import unittest
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.config_loader import load_config
from deployment.runtime.event_bus import EventBus
import time

class TestStrategyValidation(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.workspace = WorkspaceManager(cls.config.workspace.root)
        cls.provider = ProviderManager(cls.config.model_dump())
        cls.event_bus = EventBus()
        cls.controller = ResearchController(cls.workspace, cls.provider, cls.event_bus)
        
    def setUp(self):
        from unittest.mock import patch
        self.search_patch = patch('khabrichacha.tools.builtin.search_web.SearchWebTool.execute')
        self.news_patch = patch('khabrichacha.tools.builtin.search_news.SearchNewsTool.execute')
        self.fetch_patch = patch('khabrichacha.tools.builtin.fetch_page.FetchPageTool.execute')
        
        self.search_mock = self.search_patch.start()
        self.news_mock = self.news_patch.start()
        self.fetch_mock = self.fetch_patch.start()
        
        self.search_mock.return_value = [
            {"title": "Fact 1 About Query", "url": "https://example.com/1", "snippet": "Snippet content with a table. | Header 1 | Header 2 | \n |--- | --- | \n | Val 1 | Val 2 |"},
            {"title": "Fact 2 About Query", "url": "https://example.com/2", "snippet": "Snippet content 2."}
        ]
        self.news_mock.return_value = [
            {"title": "News 1", "url": "https://news.example.com/1", "snippet": "News snippet"}
        ]
        self.fetch_mock.return_value = {
            "content": "Page content with table data:\n| Column A | Column B |\n|--- | --- |\n| 123 | 456 |\n"
        }

    def tearDown(self):
        self.search_patch.stop()
        self.news_patch.stop()
        self.fetch_patch.stop()

    def _run_query(self, query: str, strategy: str):
        req = ResearchRequest(
            mission=query,
            provider="ollama", # or the configured provider
            model="qwen2.5:3b",
            strategy_override=strategy,
            workspace=str(self.workspace.root),
            metadata={"auto_regenerated": True}
        )
        return self.controller.start_research(req)

    def test_fast_strategy(self):
        start = time.time()
        res = self._run_query("What is HTTP?", "FAST")
        dur = time.time() - start
        self.assertTrue(res.success)
        self.assertEqual(res.strategy_used, "FAST")
        self.assertLess(dur, 15.0) # FAST target is < 2s but we give some buffer
        
        # Verify trace skipped planner
        trace = res.statistics.trace_data
        self.assertIn("Planner", trace.get("modules_skipped", []))
        
    def test_lookup_strategy(self):
        start = time.time()
        res = self._run_query("Capital of Japan", "LOOKUP")
        dur = time.time() - start
        self.assertTrue(res.success)
        self.assertEqual(res.strategy_used, "LOOKUP")
        self.assertLess(dur, 15.0) # Target <5s

    def test_structured_strategy(self):
        start = time.time()
        res = self._run_query("India budget 2024", "STRUCTURED")
        dur = time.time() - start
        self.assertTrue(res.success)
        self.assertEqual(res.strategy_used, "STRUCTURED")
        
        trace = res.statistics.trace_data
        self.assertIn("Planner", trace.get("modules_skipped", []))
        self.assertIn("StructuredResolver", trace.get("modules_executed", []))
        
    def test_comparison_strategy(self):
        res = self._run_query("Compare GPT-4 and Qwen3", "COMPARISON")
        self.assertTrue(res.success)
        self.assertEqual(res.strategy_used, "COMPARISON")
        
    def test_analysis_strategy(self):
        res = self._run_query("Why is inflation increasing?", "ANALYSIS")
        self.assertTrue(res.success)
        self.assertEqual(res.strategy_used, "ANALYSIS")

if __name__ == '__main__':
    unittest.main()
