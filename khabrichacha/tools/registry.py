from typing import Dict, List, Any
from khabrichacha.tools.base import BaseTool
from loguru import logger

class ToolRegistry:
    """
    Registry for managing available tools.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Registers a tool. Raises ValueError if tool name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' is already registered.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: '{tool.name}' (v{tool.version})")
        
    def register_tool(self, tool: BaseTool) -> None:
        """
        Alias for register() to maintain backward compatibility.
        """
        self.register(tool)

    def unregister(self, tool_name: str) -> None:
        """
        Unregisters a tool by name. Raises KeyError if not found.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not found in registry.")
        del self._tools[tool_name]
        logger.info(f"Unregistered tool: '{tool_name}'")

    def get_tool(self, tool_name: str) -> BaseTool:
        """
        Retrieves a tool by name. Raises KeyError if not found.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not found in registry.")
        return self._tools[tool_name]

    def has_tool(self, tool_name: str) -> bool:
        """
        Returns True if tool is registered, False otherwise.
        """
        return tool_name in self._tools

    def list_tools(self) -> List[str]:
        """
        Returns a list of registered tool names.
        """
        return list(self._tools.keys())
        
    def get_all_tools(self) -> List[BaseTool]:
        """
        Returns a list of all registered tool objects (backward compatibility).
        """
        return list(self._tools.values())

    def list_metadata(self) -> List[Dict[str, Any]]:
        """
        Returns a list of metadata for all registered tools.
        """
        return [tool.metadata() for tool in self._tools.values()]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Validates arguments and executes the tool.
        """
        tool = self.get_tool(tool_name)
        
        logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")
        
        if not tool.validate(arguments):
            raise ValueError(f"Invalid arguments for tool '{tool_name}'. Required: {tool.inputs}")
            
        try:
            result = tool.execute(arguments)
            logger.info(f"Successfully executed tool '{tool_name}'.")
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            raise
