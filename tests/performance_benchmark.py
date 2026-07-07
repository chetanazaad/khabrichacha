import time
import os
from deployment.config_loader import load_config
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.runtime.event_bus import EventBus
from loguru import logger

def benchmark():
    config = load_config()
    workspace = WorkspaceManager(config.workspace.root)
    provider = ProviderManager(config.model_dump())
    event_bus = EventBus()
    controller = ResearchController(workspace, provider, event_bus)

    reqs = [
        ("FAST", "What is HTTP?"),
        ("LOOKUP", "Capital of Japan"),
        ("STRUCTURED", "India budget 2024 tables"),
        ("ANALYSIS", "Why is inflation increasing?")
    ]

    print(f"{'Strategy':<15} | {'Elapsed (s)':<15} | {'Target':<15} | {'Pass'}")
    print("-" * 60)
    
    for strategy, query in reqs:
        req = ResearchRequest(
            mission=query,
            provider="ollama",  # Assuming Ollama runs locally
            model="qwen2.5:3b", # Target fast model for benchmarks
            strategy_override=strategy,
            workspace=str(workspace.root)
        )
        
        try:
            start = time.time()
            res = controller.start_research(req)
            dur = time.time() - start
            
            targets = {
                "FAST": 5.0, # LLM generation itself might take ~1-3s, so < 5.0 is a reasonable benchmark limit.
                "LOOKUP": 10.0,
                "STRUCTURED": 20.0,
                "ANALYSIS": 25.0
            }
            target = targets.get(strategy, 60.0)
            passed = "PASS" if dur <= target else "FAIL"
            
            print(f"{strategy:<15} | {dur:<15.2f} | < {target:<13} | {passed}")
        except Exception as e:
            print(f"{strategy:<15} | FAILED ({e})")

if __name__ == "__main__":
    benchmark()
