import unittest
import time
from unittest.mock import patch, MagicMock
from pathlib import Path
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.config_loader import load_config
from deployment.runtime.event_bus import EventBus
from khabrichacha.tools.builtin.search_web import SearchNetworkError, SearchProviderError

class TestSearchDiagnostics(unittest.TestCase):
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

    def test_invalid_model_validation(self):
        """Verify requesting an invalid model/provider raises ValueError."""
        req = ResearchRequest(
            mission="What is the capital of France?",
            provider="ollama",
            model="non_existent_model_xyz",
            workspace=str(self.workspace.root)
        )
        with self.assertRaises(ValueError) as ctx:
            self.controller.start_research(req)
        self.assertIn("Model 'non_existent_model_xyz' is not available", str(ctx.exception))

    def test_invalid_provider_validation(self):
        """Verify requesting an invalid provider raises ValueError."""
        req = ResearchRequest(
            mission="What is the capital of France?",
            provider="invalid_provider_xyz",
            model="qwen2.5:3b",
            workspace=str(self.workspace.root)
        )
        with self.assertRaises(ValueError) as ctx:
            self.controller.start_research(req)
        self.assertIn("Provider 'invalid_provider_xyz' is not available", str(ctx.exception))

    def test_temporary_session_and_promotion(self):
        """Verify temporary session creation and subsequent promotion to project."""
        req = ResearchRequest(
            mission="Simple question lookup test",
            provider="ollama",
            model="qwen2.5:3b",
            strategy_override="LOOKUP",
            workspace=str(self.workspace.root),
            metadata={"auto_regenerated": True}
        )
        res = self.controller.start_research(req)
        self.assertTrue(res.success)
        self.assertTrue(res.project_id.startswith("temp_session_"))
        
        # Verify it exists in temp, not projects
        temp_path = self.workspace.temp / res.project_id
        project_path = self.workspace.projects / res.project_id
        self.assertTrue(temp_path.exists())
        self.assertFalse(project_path.exists())
        
        # Promote session
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(self.workspace)
        pm.promote_session_to_project(res.project_id)
        
        self.assertFalse(temp_path.exists())
        self.assertTrue(project_path.exists())
        
        # Clean up
        pm.delete_project(res.project_id)

    def test_prompt_budgeting(self):
        """Verify prompt is adaptive and respects limits."""
        query = "Test query"
        evidence = ["Evidence 1" * 100, "Evidence 2" * 100]
        instructions = "Test instructions"
        
        # Budget of 200 tokens = 800 characters
        prompt = self.controller.enforce_adaptive_prompt_budget(query, evidence, instructions, 200)
        self.assertLessEqual(len(prompt), 800)

if __name__ == '__main__':
    unittest.main()
