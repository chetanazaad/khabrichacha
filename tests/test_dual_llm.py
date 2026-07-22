import pytest
from deployment.runtime.models.research_request import ResearchRequest

def test_research_request_dual_model_defaults():
    req = ResearchRequest(
        mission="Test mission",
        provider="gemini",
        model="gemini-2.0-flash",
        workspace="./projects"
    )
    assert req.ingestion_provider == "gemini"
    assert req.ingestion_model == "gemini-2.0-flash"
    assert req.analysis_provider == "gemini"
    assert req.analysis_model == "gemini-2.0-flash"

def test_research_request_explicit_dual_models():
    req = ResearchRequest(
        mission="Test mission",
        provider="gemini",
        model="gemini-2.0-pro",
        ingestion_provider="ollama",
        ingestion_model="llama3",
        analysis_provider="gemini",
        analysis_model="gemini-2.0-pro",
        workspace="./projects"
    )
    assert req.ingestion_provider == "ollama"
    assert req.ingestion_model == "llama3"
    assert req.analysis_provider == "gemini"
    assert req.analysis_model == "gemini-2.0-pro"
