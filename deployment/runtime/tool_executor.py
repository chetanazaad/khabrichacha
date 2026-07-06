"""
Tool Executor

Wraps the ToolRegistry to add middleware support (caching, logging, asset persistence)
without modifying the core registry implementation.
"""

from typing import Any, Dict, List
from khabrichacha.tools.registry import ToolRegistry
from deployment.runtime.tool_execution_middleware import MiddlewarePipeline, MiddlewareContext, ToolMiddleware


class ToolExecutor:
    """
    Executes tools by passing them through a middleware pipeline before
    calling the underlying ToolRegistry.
    """

    def __init__(self, registry: ToolRegistry, project_id: str, workspace_path: str):
        self.registry = registry
        self.project_id = project_id
        self.workspace_path = workspace_path
        self.middlewares: List[ToolMiddleware] = []
        self._pipeline = MiddlewarePipeline(self.middlewares)

    def add_middleware(self, middleware: ToolMiddleware) -> None:
        """Add a middleware to the execution pipeline."""
        self.middlewares.append(middleware)

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool through the middleware pipeline.
        """
        context = MiddlewareContext(
            tool_name=tool_name, 
            arguments=arguments, 
            project_id=self.project_id, 
            workspace_path=self.workspace_path
        )
        
        # The actual execution callback that calls the core registry
        def _execute_func():
            return self.registry.execute(tool_name, arguments)
            
        return self._pipeline.execute(context, _execute_func)

    # Delegate non-execution methods directly to the registry
    
    def register(self, tool: Any) -> None:
        self.registry.register(tool)

    def register_tool(self, tool: Any) -> None:
        self.registry.register_tool(tool)

    def has_tool(self, tool_name: str) -> bool:
        return self.registry.has_tool(tool_name)
        
    def get_tool(self, tool_name: str) -> Any:
        return self.registry.get_tool(tool_name)
        
    def list_tools(self) -> List[str]:
        return self.registry.list_tools()
        
    def list_metadata(self) -> List[Dict[str, Any]]:
        return self.registry.list_metadata()
