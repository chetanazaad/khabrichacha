"""
KhabriChacha — Provider Manager

Discovers, validates, and exposes only usable LLM providers and models.
No filesystem logic. No UI code. Lives entirely inside the providers package.
"""

import os
import time
from typing import Any, Dict, List, Tuple, Optional
from loguru import logger
from deployment.runtime.models.research_strategy import ResearchStrategy


class ProviderManager:
    """
    Automatically detects OpenAI, Gemini, OpenRouter, Ollama, and Transformers providers.
    Returns only providers that are properly configured and usable.
    Caches health discovery results to avoid UI lag.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self._providers_cache: Dict[str, Any] | None = None
        self._last_discovery_time: float = 0.0

    # ── Public API ───────────────────────────────────────────

    def refresh(self):
        """Force rediscovery of providers."""
        self.discover_providers(force_refresh=True)

    def discover_providers(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Return a dict mapping provider name → provider status and models.
        """
        current_time = time.time()
        if not force_refresh and self._providers_cache is not None:
            return self._providers_cache

        result: Dict[str, Any] = {}

        # Discover all providers
        result["openai"] = self._probe_openai()
        result["gemini"] = self._probe_gemini()
        result["openrouter"] = self._probe_openrouter()
        result["ollama"] = self._probe_ollama()
        result["transformers"] = self._probe_transformers()

        self._providers_cache = result
        self._last_discovery_time = current_time
        
        available_providers = [k for k, v in result.items() if v["available"]]
        if not available_providers:
            logger.warning("No usable LLM providers detected.")
        else:
            logger.info(f"Usable providers: {available_providers}")
            
        return result

    def get_available_models(self) -> List[str]:
        """Return a list of 'provider/model' strings that are usable."""
        usable: List[str] = []
        providers = self.discover_providers()
        for provider_name, provider_data in providers.items():
            if provider_data.get("available", False):
                for model in provider_data.get("models", []):
                    usable.append(f"{provider_name}/{model['name']}")
        return usable

    def discover_providers_and_models(self) -> Dict[str, List[str]]:
        """Legacy compatibility method returning dict of provider -> list of model names."""
        result: Dict[str, List[str]] = {}
        providers = self.discover_providers()
        for p, data in providers.items():
            if data["available"]:
                result[p] = [m["name"] for m in data["models"]]
        return result

    def get_best_model_for_strategy(self, strategy: ResearchStrategy) -> Tuple[Optional[str], Optional[str]]:
        """
        Selects the best available (provider, model) combination based on the capabilities
        required by the ResearchStrategy.
        """
        providers = self.discover_providers()
        
        # 1. Gather all usable models with their capabilities
        candidates = []
        for provider_name, p_data in providers.items():
            if not p_data.get("available", False):
                continue
            for model in p_data.get("models", []):
                candidates.append({
                    "provider": provider_name,
                    "model": model["name"],
                    "capabilities": model.get("capabilities", {}),
                    "context": model.get("context_length", 128000)
                })
                
        if not candidates:
            return None, None
            
        # 2. Filter based on strict requirements
        filtered = []
        for c in candidates:
            caps = c["capabilities"]
            
            # STRUCTURED requires JSON mode
            if strategy.strategy_name == "STRUCTURED" and not caps.get("json_mode", False):
                continue
                
            # DEEP_RESEARCH and RESEARCH ideally use reasoning models if available, but not strictly required unless we enforce it.
            # However, if it requires_reasoning flag is heavy, we might prefer it.
            # Let's enforce it if intent is complex and reasoning model exists.
            if strategy.strategy_name == "DEEP_RESEARCH" and caps.get("reasoning", False) is False:
                # We won't strictly drop them yet, but we'll score them lower
                pass
                
            filtered.append(c)
            
        if not filtered:
            filtered = candidates # Fallback if filters are too strict
            
        # 3. Rank the candidates
        def score_model(c):
            score = 0
            caps = c["capabilities"]
            s_name = strategy.strategy_name
            
            if s_name in ["FAST", "LOOKUP", "STRUCTURED"]:
                # Prefer fast models (usually non-reasoning, with json_mode)
                if not caps.get("reasoning", False):
                    score += 50
                if caps.get("json_mode", False):
                    score += 20
            elif s_name in ["COMPARISON", "ANALYSIS", "RESEARCH"]:
                # Prefer models with large context and good reasoning, but not necessarily slow "thinking" models
                score += c["context"] / 100000.0
                if caps.get("reasoning", False):
                    score += 30
            elif s_name == "DEEP_RESEARCH":
                # Prefer heavy reasoning models
                if caps.get("reasoning", False):
                    score += 100
                score += c["context"] / 100000.0
                
            return score
            
        best = max(filtered, key=score_model)
        return best["provider"], best["model"]

    def parse_ui_option(self, option: str) -> Tuple[str, str]:
        """Parse a 'provider/model' string back into (provider, model)."""
        if "/" in option:
            parts = option.split("/", 1)
            return parts[0], parts[1]
        return "openai", option

    def invalidate_cache(self):
        """Force re-discovery on next call."""
        self._providers_cache = None
        self._last_discovery_time = 0.0

    # ── Probe helpers ────────────────────────────────────────

    def _create_provider_response(
        self, installed: bool, configured: bool, available: bool, 
        reason: str, models: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "installed": installed,
            "configured": configured,
            "available": available,
            "unavailable_reason": reason,
            "models": models
        }

    def _probe_openai(self) -> Dict[str, Any]:
        try:
            import openai  # noqa: F401
            installed = True
        except ImportError:
            return self._create_provider_response(False, False, False, "openai package not installed", [])

        api_key = (
            self.config.get("providers", {}).get("openai", {}).get("api_key")
            or os.environ.get("OPENAI_API_KEY")
        )
        if not api_key:
            return self._create_provider_response(True, False, False, "OPENAI_API_KEY missing", [])

        # Hardcoded for now, real implementation could query client.models.list()
        models = [
            {"name": "gpt-4o", "context_length": 128000, "capabilities": {"reasoning": False, "vision": True, "tool_calling": True, "streaming": True, "json_mode": True}},
            {"name": "gpt-4o-mini", "context_length": 128000, "capabilities": {"reasoning": False, "vision": True, "tool_calling": True, "streaming": True, "json_mode": True}},
            {"name": "o1-preview", "context_length": 128000, "capabilities": {"reasoning": True, "vision": False, "tool_calling": False, "streaming": False, "json_mode": False}},
            {"name": "o1-mini", "context_length": 128000, "capabilities": {"reasoning": True, "vision": False, "tool_calling": False, "streaming": False, "json_mode": False}}
        ]
        return self._create_provider_response(True, True, True, "", models)

    def _probe_gemini(self) -> Dict[str, Any]:
        try:
            import google.generativeai  # noqa: F401
            installed = True
        except ImportError:
            return self._create_provider_response(False, False, False, "google-generativeai package not installed", [])

        api_key = (
            self.config.get("providers", {}).get("gemini", {}).get("api_key")
            or os.environ.get("GEMINI_API_KEY")
        )
        if not api_key:
            return self._create_provider_response(True, False, False, "GEMINI_API_KEY missing", [])

        models = [
            {"name": "gemini-2.0-flash", "context_length": 1048576, "capabilities": {"reasoning": False, "vision": True, "tool_calling": True, "streaming": True, "json_mode": True}},
            {"name": "gemini-2.0-pro-exp-02-05", "context_length": 2097152, "capabilities": {"reasoning": False, "vision": True, "tool_calling": True, "streaming": True, "json_mode": True}},
            {"name": "gemini-2.0-flash-thinking-exp-01-21", "context_length": 1048576, "capabilities": {"reasoning": True, "vision": False, "tool_calling": False, "streaming": True, "json_mode": False}}
        ]
        return self._create_provider_response(True, True, True, "", models)

    def _probe_openrouter(self) -> Dict[str, Any]:
        try:
            import openai  # OpenRouter uses the OpenAI client
            installed = True
        except ImportError:
            return self._create_provider_response(False, False, False, "openai package not installed (required for OpenRouter)", [])

        api_key = (
            self.config.get("providers", {}).get("openrouter", {}).get("api_key")
            or os.environ.get("OPENROUTER_API_KEY")
        )
        if not api_key:
            return self._create_provider_response(True, False, False, "OPENROUTER_API_KEY missing", [])

        models = [
            {"name": "anthropic/claude-3.5-sonnet", "context_length": 200000, "capabilities": {"reasoning": False, "vision": True, "tool_calling": True, "streaming": True, "json_mode": True}},
            {"name": "anthropic/claude-3.7-sonnet", "context_length": 200000, "capabilities": {"reasoning": True, "vision": True, "tool_calling": True, "streaming": True, "json_mode": True}},
            {"name": "deepseek/deepseek-r1", "context_length": 64000, "capabilities": {"reasoning": True, "vision": False, "tool_calling": True, "streaming": True, "json_mode": True}}
        ]
        return self._create_provider_response(True, True, True, "", models)

    def _probe_ollama(self) -> Dict[str, Any]:
        try:
            import requests
            installed = True
        except ImportError:
            return self._create_provider_response(False, False, False, "requests package not installed", [])

        base_url = (
            self.config.get("providers", {}).get("ollama", {}).get("base_url")
            or "http://localhost:11434"
        )
        
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    model_name = m.get("name", "")
                    if model_name:
                        # Exclude embedding-only models from LLM generation dropdowns
                        m_lower = model_name.lower()
                        if any(kw in m_lower for kw in ["embed", "bge", "minilm", "e5", "nomic-embed"]):
                            continue
                        reasoning = "r1" in m_lower or "reasoning" in m_lower
                        models.append({
                            "name": model_name,
                            "context_length": 32768,
                            "capabilities": {
                                "reasoning": reasoning,
                                "vision": False,
                                "tool_calling": True,
                                "streaming": True,
                                "json_mode": True
                            }
                        })
                if models:
                    return self._create_provider_response(True, True, True, "", models)
                else:
                    return self._create_provider_response(True, True, False, "Ollama running but no models installed", [])
            else:
                return self._create_provider_response(True, True, False, f"Ollama API returned status {resp.status_code}", [])
        except Exception as e:
            return self._create_provider_response(True, True, False, f"Ollama service unreachable at {base_url}", [])

    def _probe_transformers(self) -> Dict[str, Any]:
        """Check if transformers and torch are importable."""
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            installed = True
        except ImportError:
            return self._create_provider_response(False, False, False, "transformers or torch package not installed", [])

        models = [
            {"name": "local/transformers", "context_length": 8192, "capabilities": {"reasoning": False, "vision": False, "tool_calling": False, "streaming": False, "json_mode": False}}
        ]
        return self._create_provider_response(True, True, True, "", models)
