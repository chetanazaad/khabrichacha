from khabrichacha.llm.base import BaseLLMProvider
from typing import List, Dict, Any, Optional
from loguru import logger
import requests

class OllamaProvider(BaseLLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "llama3")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        logger.info(f"Ollama generate request for model {self.model} at {self.base_url}")
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.get("temperature", 0.7),
                "num_predict": self.config.get("max_tokens", 2048)
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                return f"Error: Ollama request failed with status code {response.status_code}: {response.text}"
        except Exception as e:
            logger.error(f"Ollama generate call failed: {e}")
            return f"[Mock Ollama {self.model}] response to prompt: {prompt}"

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        logger.info(f"Ollama chat request for model {self.model} at {self.base_url}")
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.get("temperature", 0.7),
                "num_predict": self.config.get("max_tokens", 2048)
            }
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "")
            else:
                return f"Error: Ollama chat failed with status code {response.status_code}: {response.text}"
        except Exception as e:
            logger.error(f"Ollama chat call failed: {e}")
            return f"[Mock Ollama {self.model}] response to chat history of length {len(messages)}"
