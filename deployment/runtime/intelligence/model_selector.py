from typing import Any
from pydantic import BaseModel
from deployment.runtime.models.research_strategy import ResearchStrategy

class ModelRecommendation(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    reason: str = ""

class ModelSelector:
    """Recommends LLM models based on strategy type, capability requirements (reasoning/context), and budget."""

    def select(self, strategy: ResearchStrategy, provider_manager: Any) -> ModelRecommendation:
        # Load available models
        try:
            available_models = provider_manager.get_available_models()
        except Exception:
            available_models = []

        # Find usable options from active providers
        # available_models is list of 'provider/model_name'
        # e.g., ["openai/gpt-4o", "gemini/gemini-2.0-flash", "ollama/llama3"]

        strategy_name = strategy.strategy_name
        
        # 1. Deep Reasoning query -> select reasoning models if available (thinking, o1, r1)
        if strategy_name in ["DEEP_RESEARCH", "ANALYSIS"]:
            for m in available_models:
                if any(x in m.lower() for x in ["thinking", "o1", "r1"]):
                    provider, name = m.split("/", 1)
                    return ModelRecommendation(
                        provider=provider,
                        model=name,
                        reason="Selected reasoning-capable model for analytical complexity."
                    )
            # Fallback to high quality Pro models
            for m in available_models:
                if any(x in m.lower() for x in ["gpt-4o", "gemini-2.0-pro-exp"]):
                    provider, name = m.split("/", 1)
                    return ModelRecommendation(
                        provider=provider,
                        model=name,
                        reason="Selected pro model for analytical depth."
                    )

        # 2. Fast Answer / Lookup / Structured -> select lightweight fast model
        if strategy_name in ["FAST", "LOOKUP", "STRUCTURED"]:
            for m in available_models:
                if any(x in m.lower() for x in ["flash", "-mini", "llama3"]):
                    provider, name = m.split("/", 1)
                    return ModelRecommendation(
                        provider=provider,
                        model=name,
                        reason="Selected high-speed, cost-efficient model for quick response."
                    )

        # Default fallback to first available
        if available_models:
            provider, name = available_models[0].split("/", 1)
            return ModelRecommendation(
                provider=provider,
                model=name,
                reason="Defaulting to first available model."
            )

        return ModelRecommendation(
            provider="openai",
            model="gpt-4o-mini",
            reason="Hardcoded fallback."
        )
