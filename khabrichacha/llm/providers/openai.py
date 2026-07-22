from khabrichacha.llm.base import BaseLLMProvider
from typing import List, Dict, Any, Optional
from loguru import logger
import os

class OpenAIProvider(BaseLLMProvider):
    #: Subclasses (e.g. OpenRouterProvider) can override these to point at an
    #: OpenAI-API-compatible endpoint under a different API key env var,
    #: without duplicating the request logic below.
    ENV_API_KEY = "OPENAI_API_KEY"
    DEFAULT_BASE_URL = None  # None = OpenAI's own default endpoint
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv(self.ENV_API_KEY)
        self.model = config.get("model", self.DEFAULT_MODEL)
        self.base_url = config.get("base_url", self.DEFAULT_BASE_URL)
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                client_kwargs = {"api_key": self.api_key}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                self.client = OpenAI(**client_kwargs)
            except ImportError:
                raise ValueError("openai package not installed. Cannot use OpenAIProvider.")
        else:
            raise ValueError(f"No API key provided (expected env var '{self.ENV_API_KEY}'). Real model is required; mock mode has been disabled.")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        logger.info(f"OpenAI generate request with model {self.model}")
        if self.client:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            return self.chat(messages, **kwargs)
        return f"[Mock OpenAI {self.model}] response to prompt: {prompt}"

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        logger.info(f"OpenAI chat request with model {self.model}")
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.config.get("temperature", 0.7),
                    max_tokens=self.config.get("max_tokens", 2048),
                    **kwargs
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}")
                return f"Error: OpenAI call failed: {e}"
        return f"[Mock OpenAI {self.model}] response to chat history of length {len(messages)}"


class OpenRouterProvider(OpenAIProvider):
    """
    OpenRouter speaks the same Chat Completions dialect as OpenAI, so this
    only needs to point the client at OpenRouter's endpoint and read its own
    API key/env var and default model — everything else is inherited as-is.
    OpenRouter has several free-tier models, which fits this project's
    "free" goal well.
    """
    ENV_API_KEY = "OPENROUTER_API_KEY"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
