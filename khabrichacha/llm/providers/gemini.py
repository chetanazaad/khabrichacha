from khabrichacha.llm.base import BaseLLMProvider
from typing import List, Dict, Any, Optional
from loguru import logger
import os

class GeminiProvider(BaseLLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("GEMINI_API_KEY")
        self.model_name = config.get("model", "gemini-1.5-pro")
        self.client = None
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
            except ImportError:
                logger.warning("google-generativeai package not installed. GeminiProvider will run in mock mode.")
        else:
            logger.warning("No API key provided for Gemini. Running in mock mode.")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        logger.info(f"Gemini generate request with model {self.model_name}")
        if self.client:
            try:
                config = {}
                if "temperature" in self.config:
                    config["temperature"] = self.config["temperature"]
                if "max_tokens" in self.config:
                    config["max_output_tokens"] = self.config["max_tokens"]
                
                model = self.client.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_prompt
                )
                response = model.generate_content(prompt, generation_config=config, **kwargs)
                return response.text
            except Exception as e:
                logger.error(f"Gemini generation failed: {e}")
                return f"Error: Gemini generation failed: {e}"
        return f"[Mock Gemini {self.model_name}] response to prompt: {prompt}"

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        logger.info(f"Gemini chat request with model {self.model_name}")
        if self.client:
            try:
                contents = []
                system_instruction = None
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "system":
                        system_instruction = content
                    else:
                        gemini_role = "user" if role == "user" else "model"
                        contents.append({"role": gemini_role, "parts": [content]})
                
                config = {}
                if "temperature" in self.config:
                    config["temperature"] = self.config["temperature"]
                if "max_tokens" in self.config:
                    config["max_output_tokens"] = self.config["max_tokens"]

                model = self.client.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_instruction
                )
                response = model.generate_content(contents, generation_config=config, **kwargs)
                return response.text
            except Exception as e:
                logger.error(f"Gemini chat failed: {e}")
                return f"Error: Gemini chat failed: {e}"
        return f"[Mock Gemini {self.model_name}] response to chat history of length {len(messages)}"
