import time
import os
from deployment.config_loader import load_config
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.runtime.event_bus import EventBus
from loguru import logger


def benchmark_component_timing():
    """Measure initialization timing for each component."""
    print("\n=== Component Initialization Timing ===\n")

    t = time.time()
    config = load_config()
    t_config = (time.time() - t) * 1000
    print(f"  Configuration Load:     {t_config:>8.2f} ms")

    # second call should be cached
    t = time.time()
    config2 = load_config()
    t_cached = (time.time() - t) * 1000
    cache_hit = "cached" if config is config2 else "NEW INSTANCE"
    print(f"  Config Cache (2nd call): {t_cached:>8.2f} ms ({cache_hit})")

    t = time.time()
    workspace = WorkspaceManager(config.workspace.root)
    t_ws = (time.time() - t) * 1000
    print(f"  WorkspaceManager:       {t_ws:>8.2f} ms")

    t = time.time()
    provider = ProviderManager(config.model_dump())
    t_prov = (time.time() - t) * 1000
    print(f"  ProviderManager:        {t_prov:>8.2f} ms")

    t = time.time()
    providers = provider.discover_providers()
    t_discovery = (time.time() - t) * 1000
    print(f"  Provider Discovery:     {t_discovery:>8.2f} ms")

    t = time.time()
    event_bus = EventBus()
    t_eb = (time.time() - t) * 1000
    print(f"  EventBus:               {t_eb:>8.2f} ms")

    t = time.time()
    controller = ResearchController(workspace, provider, event_bus)
    t_ctrl = (time.time() - t) * 1000
    print(f"  ResearchController:     {t_ctrl:>8.2f} ms")
    print(f"    ToolRegistry:         singleton")
    print(f"    LLMManager:           singleton")

    total = t_config + t_ws + t_prov + t_discovery + t_eb + t_ctrl
    print(f"\n  Total Init:             {total:>8.2f} ms")
    return controller


def benchmark_strategy(config: object, workspace: object, provider: object, event_bus: object, controller: object):
    reqs = [
        ("FAST", "What is HTTP?"),
        ("LOOKUP", "Capital of Japan"),
        ("STRUCTURED", "India budget 2024 tables"),
        ("ANALYSIS", "Why is inflation increasing?"),
    ]

    print(f"\n{'Strategy':<15} | {'Elapsed (s)':<15} | {'Target':<15} | {'Pass'}")
    print("-" * 70)

    for strategy, query in reqs:
        req = ResearchRequest(
            mission=query,
            provider="ollama",
            model="qwen2.5:3b",
            strategy_override=strategy,
            workspace=str(workspace.root),
        )

        try:
            start = time.time()
            res = controller.start_research(req)
            dur = time.time() - start

            targets = {
                "FAST": 5.0,
                "LOOKUP": 10.0,
                "STRUCTURED": 20.0,
                "ANALYSIS": 25.0,
            }
            target = targets.get(strategy, 60.0)
            passed = "PASS" if dur <= target else "FAIL"

            print(f"{strategy:<15} | {dur:<15.2f} | < {target:<13} | {passed}")
        except Exception as e:
            print(f"{strategy:<15} | FAILED ({e})")


def main():
    controller = benchmark_component_timing()

    config = load_config()
    workspace = WorkspaceManager(config.workspace.root)
    provider = ProviderManager(config.model_dump())
    event_bus = EventBus()

    benchmark_strategy(config, workspace, provider, event_bus, controller)

    # Summary
    print("\n=== Summary ===")
    print("Configuration Load:    <component timing above>")
    print("Provider Discovery:    <component timing above>")
    print("Tool Registration:     singleton (1 registration)")
    print("Retriever:             per-query (see strategy results)")
    print("Search:                per-query (see strategy results)")
    print("Fetch:                 per-query (see strategy results)")
    print("LLM Generation:        per-query (see strategy results)")
    print("Total:                 <component timing above> + per-query")


if __name__ == "__main__":
    main()
