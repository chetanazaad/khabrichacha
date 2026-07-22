import sys
import time
import psutil
import json
from pathlib import Path
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest
from deployment.config_loader import load_config
from deployment.runtime.event_bus import EventBus

def generate_coverage_report(traces, filepath="pipeline_coverage.md"):
    module_stats = {}
    total_queries = len(traces)
    
    for t in traces:
        for m in t.get("modules_executed", []):
            if m not in module_stats:
                module_stats[m] = {"calls": 0, "time": 0.0, "skipped": 0}
            module_stats[m]["calls"] += 1
            module_stats[m]["time"] += t.get("module_times", {}).get(m, 0.0)
            
        for m in t.get("modules_skipped", []):
            if m not in module_stats:
                module_stats[m] = {"calls": 0, "time": 0.0, "skipped": 0}
            module_stats[m]["skipped"] += 1

    lines = ["# Pipeline Coverage Report\n"]
    for m, stats in module_stats.items():
        calls = stats["calls"]
        skipped = stats["skipped"]
        total_attempts = calls + skipped
        avg_time = (stats["time"] / calls) if calls > 0 else 0
        skip_pct = (skipped / total_attempts) * 100 if total_attempts > 0 else 0
        
        lines.append(f"### {m}")
        lines.append(f"- Calls: {calls}")
        lines.append(f"- Average Runtime: {avg_time:.2f} ms")
        lines.append(f"- Skipped: {skip_pct:.1f}%")
        lines.append("")
        
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    print(f"Coverage report generated: {filepath}")

def run_benchmarks():
    config = load_config()
    workspace = WorkspaceManager(config.workspace.root)
    provider = ProviderManager(config.model_dump())
    event_bus = EventBus()
    controller = ResearchController(workspace, provider, event_bus)
    
    queries = [
        ("What is HTTP?", "FAST"),
        ("Capital of Japan", "LOOKUP"),
        ("India budget 2024", "STRUCTURED"),
        ("Compare GPT-4 and Qwen3", "COMPARISON")
    ]
    
    traces = []
    
    print("Running benchmarks...")
    for q, strategy in queries:
        req = ResearchRequest(
            mission=q,
            provider="ollama", # Update if needed
            model="llama3",
            strategy_override=strategy,
            workspace=str(workspace.root)
        )
        
        start_cpu = psutil.cpu_percent(interval=None)
        start_mem = psutil.virtual_memory().used
        
        start = time.time()
        res = controller.start_research(req)
        dur = time.time() - start
        
        end_cpu = psutil.cpu_percent(interval=None)
        end_mem = psutil.virtual_memory().used
        
        print(f"Strategy: {strategy:10s} | Latency: {dur:5.2f}s | CPU: {end_cpu}% | RAM Delta: {(end_mem - start_mem)/1024/1024:.1f}MB")
        
        if res.success and res.statistics.trace_data:
            traces.append(res.statistics.trace_data)
            
    generate_coverage_report(traces)
    
if __name__ == "__main__":
    run_benchmarks()
