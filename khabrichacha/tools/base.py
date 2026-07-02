from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name of the tool, matching register keys.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Detailed description explaining when and how the LLM should invoke the tool.
        """
        pass

    @property
    def schema(self) -> Dict[str, Any]:
        """
        Optional JSON schema defining input arguments. Useful for structured tool calls.
        """
        return {}

    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> str:
        """
        Main execution target for the tool logic. Returns the results formatted as a string.
        """
        pass
