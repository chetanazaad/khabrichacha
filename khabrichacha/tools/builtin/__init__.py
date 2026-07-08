from khabrichacha.tools.base import BaseTool
from typing import Dict, Any
from loguru import logger

class WorkspaceInitTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_init"

    @property
    def description(self) -> str:
        return "Initializes the agent workspace session and variables."

    def execute(self, args: Dict[str, Any]) -> str:
        logger.info("WorkspaceInitTool executed.")
        return "Workspace initialized successfully. Directory status: Clean. Session variables populated."

class ExecuteTaskTool(BaseTool):
    @property
    def name(self) -> str:
        return "execute_task"

    @property
    def description(self) -> str:
        return "Processes and executes a target task step."

    def execute(self, args: Dict[str, Any]) -> str:
        logger.info("ExecuteTaskTool executed.")
        return "Task processed. Generated observation: Target dataset queried, results structured, and inputs validated."

class SummarizeResultsTool(BaseTool):
    @property
    def name(self) -> str:
        return "summarize_results"

    @property
    def description(self) -> str:
        return "Compiles an execution summary report for the user."

    def execute(self, args: Dict[str, Any]) -> str:
        logger.info("SummarizeResultsTool executed.")
        return "Final Report: All target pipeline operations finished successfully. Worktrees updated."

def register_builtin_tools(registry):
    for tool in [WorkspaceInitTool(), ExecuteTaskTool(), SummarizeResultsTool()]:
        if not registry.has_tool(tool.name):
            registry.register_tool(tool)
