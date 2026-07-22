from khabrichacha.llm.base import BaseLLMProvider
from typing import List, Dict, Any, Optional
from loguru import logger
import requests

class OllamaProvider(BaseLLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "qwen2.5:3b")
        # CPU-only inference for the long structured/planning prompts this app
        # sends can easily exceed a naive 30s timeout, especially on Colab or
        # older hardware — 120s is a safer default. Still overridable per-call
        # via config["timeout"].
        self.timeout = config.get("timeout", 120)

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
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                raise RuntimeError(f"Ollama request failed with status code {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Ollama generate call timed out after {self.timeout}s")
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout}s. The model may be slow on this "
                f"hardware — try a smaller model, or raise llm.providers.ollama.timeout in config."
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ollama connection failed: {e}")
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Is Ollama running? "
                f"(Install from ollama.com, then `ollama pull {self.model}`.)"
            )

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
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "")
            else:
                raise RuntimeError(f"Ollama chat failed with status code {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Ollama chat call timed out after {self.timeout}s")
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout}s. The model may be slow on this "
                f"hardware — try a smaller model, or raise llm.providers.ollama.timeout in config."
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ollama connection failed: {e}")
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Is Ollama running? "
                f"(Install from ollama.com, then `ollama pull {self.model}`.)"
            )
