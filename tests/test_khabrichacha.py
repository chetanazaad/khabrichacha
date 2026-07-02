import pytest
import yaml
from pathlib import Path
from khabrichacha.core.state import State, Message
from khabrichacha.core.session import Session
from khabrichacha.tools.registry import ToolRegistry
from khabrichacha.tools.base import BaseTool
from khabrichacha.llm.manager import LLMManager
from typing import Dict, Any

def test_state_creation():
    state = State(session_id="test_sess")
    assert state.session_id == "test_sess"
    assert len(state.messages) == 0
    state.add_message("user", "Hello world")
    assert len(state.messages) == 1
    assert state.messages[0].role == "user"
    assert state.messages[0].content == "Hello world"

def test_session_init():
    session = Session(session_id="test_session")
    assert session.session_id == "test_session"
    assert len(session.state.messages) == 1
    assert session.state.messages[0].role == "system"

def test_tool_registry():
    registry = ToolRegistry()
    
    class MockTool(BaseTool):
        @property
        def name(self) -> str:
            return "mock_tool"
            
        @property
        def description(self) -> str:
            return "Mock description"
            
        def execute(self, args: Dict[str, Any]) -> str:
            return "executed"
            
    mock = MockTool()
    registry.register_tool(mock)
    assert registry.has_tool("mock_tool")
    assert registry.get_tool("mock_tool").execute({}) == "executed"

def test_llm_manager():
    config = {
        "llm": {
            "default_provider": "openai",
            "temperature": 0.5,
            "max_tokens": 100
        },
        "providers": {
            "openai": {
                "model": "gpt-4"
            }
        }
    }
    manager = LLMManager(config)
    assert "openai" in manager.providers
    provider = manager.get_provider("openai")
    assert provider.model == "gpt-4"
    assert provider.config.get("temperature") == 0.5
