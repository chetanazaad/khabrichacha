from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseTool(ABC):
    """
    Abstract base class for all tools in the KhabriChacha framework.
    """

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
    def category(self) -> str:
        """
        Tool category for organization (e.g. 'search', 'utility').
        """
        return "general"

    @property
    def version(self) -> str:
        """
        Version of the tool.
        """
        return "1.0"

    @property
    def inputs(self) -> List[str]:
        """
        List of required input argument names.
        """
        return []

    @property
    def outputs(self) -> List[str]:
        """
        List of output argument names or descriptive keys.
        """
        return []

    @property
    def supports_streaming(self) -> bool:
        """
        Whether the tool supports returning streaming outputs.
        """
        return False

    @abstractmethod
    def execute(self, arguments: Dict[str, Any]) -> Any:
        """
        Main execution target for the tool logic.
        """
        pass

    def validate(self, arguments: Dict[str, Any]) -> bool:
        """
        Validates the provided arguments against the required inputs.
        """
        for req in self.inputs:
            if req not in arguments:
                return False
        return True

    def metadata(self) -> Dict[str, Any]:
        """
        Returns a structured dictionary of tool metadata.
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "supports_streaming": self.supports_streaming
        }
