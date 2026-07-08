from khabrichacha.llm.providers.openai import OpenAIProvider
from typing import Dict, Any
import os

class OpenRouterProvider(OpenAIProvider):
    """
    OpenRouter LLM provider. Uses OpenAI SDK client under the hood.
    """
    def __init__(self, config: Dict[str, Any]):
        # Ensure we use OPENROUTER_API_KEY if available
        api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        config["api_key"] = api_key
        config["base_url"] = config.get("base_url") or "https://openrouter.ai/api/v1"
        super().__init__(config)
