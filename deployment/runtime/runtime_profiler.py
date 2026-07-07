import time
import json
import os
import sys
from typing import Dict, Any, List

class RuntimeProfiler:
    """
    Profiles the instantiation and initialization of runtime components.
    Ensures lazy initialization and zero-waste execution.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RuntimeProfiler, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance
        
    def _init_state(self):
        self.trace: Dict[str, Any] = {
            "initialization_order": [],
            "execution_order": [],
            "component_costs": {},
            "memory_usage": {},
            "skipped_components": {},
            "strategy": "UNKNOWN"
        }
        self.start_time = time.time()
        
    def set_strategy(self, strategy: str):
        self.trace["strategy"] = strategy
        
    def record_init(self, component_name: str, caller: str, reason: str, duration_ms: float = 0.0):
        if component_name not in self.trace["initialization_order"]:
            self.trace["initialization_order"].append(component_name)
            
        self.trace["component_costs"][component_name] = {
            "duration_ms": duration_ms,
            "caller": caller,
            "reason": reason
        }
        
        # Estimate memory usage of the class/module if possible, here we just use 0 as placeholder 
        # since deep object graph size is hard to calculate safely in pure python.
        self.trace["memory_usage"][component_name] = "Unknown"
        
    def record_execution(self, module_name: str):
        if module_name not in self.trace["execution_order"]:
            self.trace["execution_order"].append(module_name)
            
    def record_skipped(self, component_name: str, reason: str):
        self.trace["skipped_components"][component_name] = reason

    def dump_trace(self, directory: str = ""):
        self.trace["total_runtime_ms"] = (time.time() - self.start_time) * 1000
        
        if directory:
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "runtime_trace.json")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.trace, f, indent=2)
            except Exception:
                pass
                
        return self.trace
