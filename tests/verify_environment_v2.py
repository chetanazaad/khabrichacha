import os
import unittest
from deployment.config_loader import load_config
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.runtime.event_bus import EventBus
from deployment.runtime.execution_validator import ExecutionValidator
import time

class TestExecutionPipelineV2(unittest.TestCase):
    
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
        self.fetch_patch = patch('khabrichacha.tools.builtin.fetch_page.FetchPageTool.execute')
        
        self.search_mock = self.search_patch.start()
        self.fetch_mock = self.fetch_patch.start()
        
        self.search_mock.return_value = [
            {"title": "Fact 1 About Query", "url": "https://example.com/1", "snippet": "Snippet content."}
        ]
        self.fetch_mock.return_value = {
            "content": "Page content"
        }

    def tearDown(self):
        self.search_patch.stop()
        self.fetch_patch.stop()

    def test_provider_cache(self):
        start = time.time()
        res1 = self.provider.discover_providers()
        t1 = time.time() - start
        
        start = time.time()
        res2 = self.provider.discover_providers()
        t2 = time.time() - start
        
        self.assertLess(t2, t1) # Cache should make second call extremely fast
        
    def test_lazy_initialization_fast(self):
        req = ResearchRequest(mission="What is HTTP?", provider="ollama", model="qwen2.5:3b", strategy_override="FAST", workspace=str(self.workspace.root))
        res = self.controller.start_research(req)
        
        self.assertTrue(res.success)
        
        # Verify trace file exists
        trace_path = os.path.join(res.project_path, "runtime_trace.json")
        self.assertTrue(os.path.exists(trace_path))
        
        # Validate trace rules
        is_valid = ExecutionValidator.validate_trace_file(trace_path)
        self.assertTrue(is_valid)
        
    def test_temporary_session(self):
        req = ResearchRequest(mission="What is HTTP?", provider="ollama", model="qwen2.5:3b", strategy_override="FAST", workspace=str(self.workspace.root))
        res = self.controller.start_research(req)
        
        # Assert no reports or metadata were created
        self.assertFalse(os.path.exists(os.path.join(res.project_path, "metadata.json")))
        self.assertFalse(os.path.exists(os.path.join(res.project_path, "report.md")))
        
if __name__ == '__main__':
    unittest.main()
