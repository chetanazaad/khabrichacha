"""
KhabriChacha — Configuration Loader

Merges base_config.yaml with an environment-specific override file,
validates the result through Pydantic, and returns a typed object.

Supported environments: local | colab | docker
Set via KHABRICHACHA_ENV env var (defaults to "local").
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

# ── Pydantic Config Models ──────────────────────────────────

class AppConfig(BaseModel):
    name: str = "KhabriChacha"
    version: str = "1.0.0"
    schema_version: str = "1.0"

class WorkspaceConfig(BaseModel):
    root: str = "./workspace"

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False
    dark: bool = True

class LLMConfig(BaseModel):
    default_provider: str = "gemini"
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = (
        "You are Khabri Chacha, an intelligent, helpful agent assistant. "
        "Act as a coordinator and solve user queries step by step."
    )

class ResearchConfig(BaseModel):
    depth: str = "standard"
    max_iterations: int = 5
    max_runtime_minutes: int = 15
    max_sources: int = 10
    parallel_fetch: int = 10
    language: str = "English"
    output_formats: List[str] = Field(default_factory=lambda: ["md", "json", "pdf"])

class BrowserConfig(BaseModel):
    playwright: bool = True
    chromium: bool = True
    timeout: int = 30

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: bool = True

class KhabriChachaConfig(BaseModel):
    """Top-level, strongly typed application configuration."""
    app: AppConfig = Field(default_factory=AppConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Keep the raw merged dict available for backward-compat with Session
    _raw: Dict[str, Any] = {}

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Return a flat dictionary compatible with existing Session/Orchestrator code."""
        return {
            "app": self.app.model_dump(),
            "workspace": self.workspace.model_dump(),
            "server": self.server.model_dump(),
            "llm": self.llm.model_dump(),
            "research": self.research.model_dump(),
            "browser": self.browser.model_dump(),
            "logging": self.logging.model_dump(),
        }

# ── Helper: deep merge ──────────────────────────────────────

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

# ── Singleton Cache ──────────────────────────────────────────

_cached_config: Optional[KhabriChachaConfig] = None

# ── Public API ───────────────────────────────────────────────

_CONFIG_DIR = Path(__file__).resolve().parent

def detect_environment() -> str:
    """Return the active environment name from KHABRICHACHA_ENV (default: local)."""
    return os.environ.get("KHABRICHACHA_ENV", "local").lower()

def load_config(environment: Optional[str] = None) -> KhabriChachaConfig:
    """
    Load and merge configuration files, returning a validated
    KhabriChachaConfig object.

    1. Load deployment/base_config.yaml
    2. Merge deployment/<environment>.yaml on top
    3. Validate via Pydantic

    Results are cached after first load; subsequent calls return the same instance.
    Use reload_config() to force a fresh load.
    """
    global _cached_config
    if _cached_config is not None:
        logger.debug("Returning cached configuration.")
        return _cached_config

    env = environment or detect_environment()
    base_path = _CONFIG_DIR / "base_config.yaml"
    env_path = _CONFIG_DIR / f"{env}.yaml"

    # Load base
    base_data: Dict[str, Any] = {}
    if base_path.exists():
        with open(base_path, "r", encoding="utf-8") as f:
            base_data = yaml.safe_load(f) or {}
        logger.info(f"Loaded base configuration from {base_path}")
    else:
        logger.warning(f"Base configuration not found at {base_path}; using defaults.")

    # Load environment override
    env_data: Dict[str, Any] = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            env_data = yaml.safe_load(f) or {}
        logger.info(f"Loaded '{env}' environment override from {env_path}")
    else:
        logger.warning(f"Environment override '{env}.yaml' not found; using base only.")

    merged = _deep_merge(base_data, env_data)

    try:
        config = KhabriChachaConfig.model_validate(merged)
        config._raw = merged
        _cached_config = config
        logger.info(f"Configuration validated successfully for environment '{env}'.")
        return config
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


def reload_config(environment: Optional[str] = None) -> KhabriChachaConfig:
    """Clear the cached configuration and reload from disk."""
    global _cached_config
    _cached_config = None
    return load_config(environment)
