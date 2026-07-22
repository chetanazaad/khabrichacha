"""
Tool Execution Middleware

Provides a pipeline pattern for intercepting and augmenting tool execution
without modifying the core ToolRegistry or the Tools themselves.
"""

from typing import Any, Dict, Protocol, List
from loguru import logger


class MiddlewareContext:
    """Context passed through the middleware pipeline."""
    def __init__(self, tool_name: str, arguments: Dict[str, Any], project_id: str, workspace_path: str):
        self.tool_name = tool_name
        self.arguments = arguments
        self.project_id = project_id
        self.workspace_path = workspace_path
        self.metadata: Dict[str, Any] = {}
        self.result: Any = None
        self.error: Exception | None = None
        self.is_cached: bool = False


class ToolMiddleware(Protocol):
    """Protocol for tool execution middleware."""
    def pre_execute(self, context: MiddlewareContext) -> bool:
        """
        Called before the tool executes.
        If it returns False, execution is aborted (e.g., cache hit).
        """
        ...
        
    def post_execute(self, context: MiddlewareContext) -> None:
        """Called after the tool executes successfully."""
        ...
        
    def on_error(self, context: MiddlewareContext) -> None:
        """Called if the tool raises an exception."""
        ...


class MiddlewarePipeline:
    """Executes a chain of middlewares around a tool execution."""
    
    def __init__(self, middlewares: List[ToolMiddleware]):
        self.middlewares = middlewares
        
    def execute(self, context: MiddlewareContext, execute_func: callable) -> Any:
        """
        Run the pipeline.
        execute_func should be a callable that takes no arguments and returns the tool result.
        """
        try:
            # Pre-execute phase
            should_execute = True
            for mw in self.middlewares:
                try:
                    if not mw.pre_execute(context):
                        should_execute = False
                        break
                except Exception as e:
                    logger.warning(f"Middleware {mw.__class__.__name__} failed in pre_execute: {e}")
            
            # Execute actual tool if not aborted (e.g. by cache)
            if should_execute:
                context.result = execute_func()
                
            # Post-execute phase
            for mw in reversed(self.middlewares):
                try:
                    mw.post_execute(context)
                except Exception as e:
                    logger.warning(f"Middleware {mw.__class__.__name__} failed in post_execute: {e}")
                    
            return context.result
            
        except Exception as e:
            context.error = e
            # Error phase
            for mw in reversed(self.middlewares):
                try:
                    mw.on_error(context)
                except Exception as mw_e:
                    logger.warning(f"Middleware {mw.__class__.__name__} failed in on_error: {mw_e}")
            raise e
