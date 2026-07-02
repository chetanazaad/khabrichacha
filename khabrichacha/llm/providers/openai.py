from khabrichacha.llm.base import BaseLLMProvider
from typing import List, Dict, Any, Optional
from loguru import logger
import os

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.model = config.get("model", "gpt-4o")
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai package not installed. OpenAIProvider will run in mock mode.")
        else:
            logger.warning("No API key provided for OpenAI. Running in mock mode.")

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
