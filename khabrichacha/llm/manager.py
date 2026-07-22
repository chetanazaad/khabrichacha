from typing import Dict, Any, Type, Optional
from khabrichacha.llm.base import BaseLLMProvider
from loguru import logger

class LLMManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers: Dict[str, Type[BaseLLMProvider]] = {}
        self._register_default_providers()

    def register_provider(self, name: str, provider_cls: Type[BaseLLMProvider]):
        self.providers[name] = provider_cls
        logger.info(f"Registered LLM provider: {name}")

    def _register_default_providers(self):
        # Local import to prevent circular dependency
        from khabrichacha.llm.providers.openai import OpenAIProvider, OpenRouterProvider
        from khabrichacha.llm.providers.gemini import GeminiProvider
        from khabrichacha.llm.providers.ollama import OllamaProvider
        from khabrichacha.llm.providers.transformers import TransformersProvider

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
        provider_config = self.config.get("providers", {}).get(provider_name, {}).copy()
        
        # Merge general LLM settings if provider-specific settings are missing
        llm_general = self.config.get("llm", {})
        for key in ["temperature", "max_tokens"]:
            if key in llm_general and key not in provider_config:
                provider_config[key] = llm_general[key]
                
        logger.info(f"Instantiated LLM provider: {provider_name}")
        return provider_cls(provider_config)

    def get_ingestion_provider(self) -> BaseLLMProvider:
        llm_cfg = self.config.get("llm", {})
        prov_name = llm_cfg.get("ingestion_provider") or llm_cfg.get("default_provider", "openai")
        return self.get_provider(prov_name)

    def get_analysis_provider(self) -> BaseLLMProvider:
        llm_cfg = self.config.get("llm", {})
        prov_name = llm_cfg.get("analysis_provider") or llm_cfg.get("default_provider", "openai")
        return self.get_provider(prov_name)

