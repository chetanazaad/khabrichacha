"""
Cache Manager

Handles caching of intermediate computations and tool execution results
to avoid redundant work and save costs.
"""

import os
import json
import hashlib
from typing import Any, Dict, Optional


class CacheManager:
    """Caches tool results and parsed data to disk."""

    def __init__(self, workspace_path: str, project_id: str):
        self.workspace_path = workspace_path
        self.project_id = project_id
        self.cache_dir = os.path.join(self.workspace_path, self.project_id, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _generate_key(self, operation: str, inputs: Dict[str, Any]) -> str:
        """Generate a deterministic hash key for an operation and its inputs."""
        # Sort keys to ensure deterministic JSON representation
        input_str = json.dumps(inputs, sort_keys=True)
        combined = f"{operation}:{input_str}".encode('utf-8')
        return hashlib.sha256(combined).hexdigest()

    def get_cached_result(self, operation: str, inputs: Dict[str, Any]) -> Optional[Any]:
        """
        Retrieve a cached result if it exists.
        :param operation: Name or identifier of the operation (e.g., 'extract_text', 'summarize')
        :param inputs: Dictionary of inputs to the operation
        """
        key = self._generate_key(operation, inputs)
        filepath = os.path.join(self.cache_dir, f"{key}.json")
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("result")
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def set_cached_result(self, operation: str, inputs: Dict[str, Any], result: Any) -> None:
        """
        Save a result to the cache.
        """
        key = self._generate_key(operation, inputs)
        filepath = os.path.join(self.cache_dir, f"{key}.json")
        
        # Ensure result is JSON serializable
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({"result": result}, f, indent=2, ensure_ascii=False)
        except TypeError:
            # Result contains non-serializable objects, ignore caching
            pass
