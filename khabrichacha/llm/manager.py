from typing import Dict, Any, Type, Optional
from khabrichacha.llm.base import BaseLLMProvider
from loguru import logger

class LLMManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers: Dict[str, Type[BaseLLMProvider]] = {}
        self._provider_cache = {}
        self._register_default_providers()

    def register_provider(self, name: str, provider_cls: Type[BaseLLMProvider]):
        self.providers[name] = provider_cls
        logger.info(f"Registered LLM provider: {name}")

    def _register_default_providers(self):
        # Local import to prevent circular dependency
        from khabrichacha.llm.providers.openai import OpenAIProvider
        from khabrichacha.llm.providers.gemini import GeminiProvider
        from khabrichacha.llm.providers.ollama import OllamaProvider
        from khabrichacha.llm.providers.transformers import TransformersProvider
        from khabrichacha.llm.providers.openrouter import OpenRouterProvider

        self.register_provider("openai", OpenAIProvider)
        self.register_provider("gemini", GeminiProvider)
        self.register_provider("ollama", OllamaProvider)
        self.register_provider("transformers", TransformersProvider)
        self.register_provider("openrouter", OpenRouterProvider)

    def get_provider(self, name: Optional[str] = None) -> BaseLLMProvider:
        provider_name = name or self.config.get("llm", {}).get("default_provider", "openai")
        if provider_name not in self.providers:
            raise ValueError(f"LLM Provider '{provider_name}' is not registered.")
            
        provider_cls = self.providers[provider_name]
        provider_config = self.config.get("providers", {}).get(provider_name, {})
        
        # Merge general LLM settings if provider-specific settings are missing
        llm_general = self.config.get("llm", {})
        for key in ["temperature", "max_tokens"]:
            if key in llm_general and key not in provider_config:
                provider_config[key] = llm_general[key]

        model = provider_config.get("model") or provider_config.get("model_id") or ""
        cache_key = (provider_name, model)
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]
                
        logger.info(f"Instantiated LLM provider: {provider_name}")
        provider_instance = provider_cls(provider_config)
        self._provider_cache[cache_key] = provider_instance
        return provider_instance
