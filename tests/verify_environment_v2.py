import os
import unittest
from deployment.config_loader import load_config, reload_config
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.runtime.event_bus import EventBus
from deployment.runtime.execution_validator import ExecutionValidator
from khabrichacha.tools.registry import ToolRegistry
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

    def test_config_singleton(self):
        """load_config() returns the same object on repeated calls."""
        c1 = load_config()
        c2 = load_config()
        self.assertIs(c1, c2, "load_config() should return the cached singleton instance")

    def test_config_reload(self):
        """reload_config() returns a new instance."""
        c1 = load_config()
        c2 = reload_config()
        self.assertIsNot(c1, c2, "reload_config() should return a fresh instance")
        # restore cache
        load_config()

    def test_provider_cache(self):
        """ProviderManager.discover_providers() is cached (second call is faster)."""
        start = time.time()
        res1 = self.provider.discover_providers()
        t1 = time.time() - start

        start = time.time()
        res2 = self.provider.discover_providers()
        t2 = time.time() - start

        self.assertLess(t2, t1)

    def test_tool_registry_singleton(self):
        """ResearchController._tool_registry has all tools pre-registered."""
        registry = self.controller._tool_registry
        self.assertIsInstance(registry, ToolRegistry)
        # verify all three tools are registered
        for tool_name in ("search_web", "search_news", "fetch_page"):
            with self.subTest(tool=tool_name):
                tool = registry.get_tool(tool_name)
                self.assertIsNotNone(tool, f"Tool '{tool_name}' should be pre-registered")

    def test_event_bus_warning_alias(self):
        """event_bus.warn() and event_bus.warning() both work."""
        events = []
        def collector(e):
            events.append(e)
        self.event_bus.subscribe("WARNING", collector)
        self.event_bus.warn("Test", "warn message")
        self.event_bus.warning("Test", "warning message")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].message, "warn message")
        self.assertEqual(events[1].message, "warning message")
        self.event_bus.unsubscribe("WARNING", collector)

    def test_lazy_initialization_fast(self):
        """FAST strategy executes without Session (lightweight)."""
        req = ResearchRequest(
            mission="What is HTTP?",
            provider="ollama",
            model="qwen2.5:3b",
            strategy_override="FAST",
            workspace=str(self.workspace.root),
        )
        res = self.controller.start_research(req)

        self.assertTrue(res.success)

        trace_path = os.path.join(res.project_path, "runtime_trace.json")
        self.assertTrue(os.path.exists(trace_path))

        is_valid = ExecutionValidator.validate_trace_file(trace_path)
        self.assertTrue(is_valid)

    def test_temporary_session(self):
        """FAST strategy creates a temp session (no metadata.json or report.md)."""
        req = ResearchRequest(
            mission="What is HTTP?",
            provider="ollama",
            model="qwen2.5:3b",
            strategy_override="FAST",
            workspace=str(self.workspace.root),
        )
        res = self.controller.start_research(req)

        self.assertFalse(os.path.exists(os.path.join(res.project_path, "metadata.json")))
        self.assertFalse(os.path.exists(os.path.join(res.project_path, "report.md")))

    def test_no_session_for_fast(self):
        """FAST handler should NOT create a Session (trace shows session_created: false)."""
        req = ResearchRequest(
            mission="What is HTTP?",
            provider="ollama",
            model="qwen2.5:3b",
            strategy_override="FAST",
            workspace=str(self.workspace.root),
        )
        res = self.controller.start_research(req)

        # Check trace data for runtime_info
        trace = res.statistics.trace_data
        runtime_info = trace.get("runtime_info", {})
        self.assertFalse(runtime_info.get("session_created", True),
                         "FAST strategy should have session_created: false")
        self.assertEqual(runtime_info.get("config_source"), "cached")
        self.assertEqual(runtime_info.get("tool_registry_source"), "singleton")


if __name__ == '__main__':
    unittest.main()
