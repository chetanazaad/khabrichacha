from khabrichacha.core.state import State
from typing import Optional
from uuid import uuid4
import yaml
from pathlib import Path
from loguru import logger

class Session:
    def __init__(self, session_id: Optional[str] = None, config_path: str = "config.yaml"):
        self.session_id = session_id or str(uuid4())
        self.config = self._load_config(config_path)
        self.state = State(session_id=self.session_id)
        self.runtime = {}
        self.research_state = {
            "iteration": 0,
            "completed": False,
            "total_sources": 0,
            "unique_domains": 0,
            "findings": [],
            "coverage": "0%",
            "outstanding_questions": []
        }
        
        system_prompt = self.config.get("llm", {}).get(
            "system_prompt", 
            "You are Khabri Chacha, an intelligent, helpful agent assistant. Act as a coordinator and solve user queries step by step."
        )
        self.state.add_message("system", system_prompt)
        logger.info(f"Initialized Session: {self.session_id}")

    def _load_config(self, path: str) -> dict:
        """
        Load configuration using the deployment config loader when available,
        falling back to direct YAML loading for backward compatibility.
        """
        # Try the deployment config loader first (no platform-specific logic here)
        try:
            from deployment.config_loader import load_config
            config_obj = load_config()
            logger.info("Configuration loaded via deployment.config_loader.")
            return config_obj.to_legacy_dict()
        except Exception:
            pass

        # Fallback: direct YAML loading (backward compat)
        config_file = Path(path)
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                return {}
        return {}

    def add_user_message(self, content: str):
        self.state.add_message("user", content)
        logger.debug(f"Session {self.session_id} - User: {content}")

    def add_assistant_message(self, content: str):
        self.state.add_message("assistant", content)
        logger.debug(f"Session {self.session_id} - Assistant: {content}")

    def add_tool_message(self, tool_name: str, content: str):
        self.state.add_message("tool", content, name=tool_name)
        logger.debug(f"Session {self.session_id} - Tool ({tool_name}): {content}")
