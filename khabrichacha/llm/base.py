from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseLLMProvider(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @property
    def model_identifier(self) -> Optional[str]:
        """
        Canonical model name for this provider instance, regardless of which
        attribute name the concrete subclass happens to store it under
        (OpenAI/Ollama use `.model`, Gemini uses `.model_name`, Transformers
        uses `.model_id`). Callers that need to verify "did I actually get
        the model I asked for" should use this instead of guessing attribute
        names themselves — a previous version of this guesswork silently
        broke model verification for the Transformers provider everywhere
        it was duplicated.
        """
        for attr in ("model", "model_name", "model_id"):
            value = getattr(self, attr, None)
            if value:
                return value
        return None

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        Generate a text completion for a single prompt.
        """
        pass

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate a response based on a list of chat message objects (containing 'role' and 'content').
        """
        pass
