import unittest
import os
from deployment.workspace.workspace_manager import WorkspaceManager
from deployment.config_loader import load_config
from khabrichacha.providers.provider_manager import ProviderManager

class TestRegression(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.workspace = WorkspaceManager(cls.config.workspace.root)
        cls.provider_manager = ProviderManager(cls.config.model_dump())
        
    def test_provider_discovery(self):
        providers = self.provider_manager.discover_providers()
        self.assertIn("ollama", providers)
        self.assertIn("openai", providers)
        
    def test_workspace_manager(self):
        self.assertTrue(os.path.exists(self.workspace.root))
        
    def test_load_projects(self):
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(self.workspace)
        projects = pm.list_projects()
        
        # Check if we can load the manifest for each project (regression check)
        for proj in projects:
            self.assertIsNotNone(proj.project_id)
            self.assertIsNotNone(proj.title)

if __name__ == '__main__':
    unittest.main()
