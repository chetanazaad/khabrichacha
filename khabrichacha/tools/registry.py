from typing import Dict, List
from khabrichacha.tools.base import BaseTool
from loguru import logger

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool):
        if tool.name in self._tools:
            logger.warning(f"Overwriting tool '{tool.name}' in registry.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry.")
        return self._tools[name]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_tools(self) -> List[BaseTool]:
        return list(self._tools.values())
