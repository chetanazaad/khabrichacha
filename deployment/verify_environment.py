"""
KhabriChacha — Environment Verification

Checks every subsystem and prints PASS / FAIL for each.
Can be used standalone or called from launch_colab.py.
"""

import sys
from typing import Optional
from loguru import logger


def _check(label: str, fn) -> bool:
    try:
        result = fn()
        status = "PASS" if result else "FAIL"
    except Exception as e:
        result = False
        status = f"FAIL ({e})"
    print(f"  [{status:>30}]  {label}")
    return bool(result)


def run_verification(workspace=None, config=None):
    print()
    print("=" * 60)
    print("  KhabriChacha — Environment Verification")
    print("=" * 60)

    all_passed = True

    # ── Python ───────────────────────────────────────────
    all_passed &= _check("Python >= 3.9", lambda: sys.version_info >= (3, 9))

    # ── Core Dependencies ────────────────────────────────
    deps = {
        "NiceGUI": "nicegui",
        "Loguru": "loguru",
        "Uvicorn": "uvicorn",
        "PyYAML": "yaml",
        "Pydantic": "pydantic",
        "Requests": "requests",
        "BeautifulSoup4": "bs4",
        "DuckDuckGo Search": "duckduckgo_search",
        "PyMuPDF": "fitz",
        "Readability": "readability",
        "Feedparser": "feedparser",
        "Pandas": "pandas",
        "NumPy": "numpy",
        "OpenAI SDK": "openai",
        "Google GenAI": "google.generativeai",
        "ReportLab": "reportlab",
    }
    for name, mod in deps.items():
        all_passed &= _check(f"Dependency: {name}", lambda m=mod: __import__(m) is not None)

    # ── Workspace ────────────────────────────────────────
    if workspace:
        all_passed &= _check("Workspace exists", lambda: workspace.root.exists())
        all_passed &= _check("Workspace writable", lambda: workspace.verify())
    else:
        _check("Workspace (skipped — not provided)", lambda: True)

    # ── Workspace Schema ─────────────────────────────────
    all_passed &= _check("Workspace Schema", lambda: __import__("deployment.workspace.workspace_schema") is not None)

    # ── Project Manager ──────────────────────────────────
    all_passed &= _check("Project Manager", lambda: __import__("deployment.workspace.project_manager") is not None)

    # ── Asset & Cache Managers ───────────────────────────
    all_passed &= _check("Asset Manager", lambda: __import__("deployment.workspace.asset_manager") is not None)
    all_passed &= _check("Cache Manager", lambda: __import__("deployment.workspace.cache_manager") is not None)

    # ── Provider Manager ─────────────────────────────────
    all_passed &= _check("Provider Manager", lambda: __import__("khabrichacha.providers.provider_manager") is not None)

    # ── Planner ──────────────────────────────────────────
    all_passed &= _check("Planner", lambda: __import__("khabrichacha.core.planner") is not None)

    # ── Adaptive Planner ─────────────────────────────────
    def _check_adaptive():
        from khabrichacha.core.planner import Planner
        return hasattr(Planner, "generate_adaptive_plan")
    all_passed &= _check("Adaptive Planner", _check_adaptive)

    # ── Tool Registry & Executor ─────────────────────────
    all_passed &= _check("Tool Registry", lambda: __import__("khabrichacha.tools.registry") is not None)
    all_passed &= _check("Tool Executor", lambda: __import__("deployment.runtime.tool_executor") is not None)
    all_passed &= _check("Tool Middleware", lambda: __import__("deployment.runtime.tool_execution_middleware") is not None)

    # ── Runtime Variables ────────────────────────────────
    def _check_runtime():
        from khabrichacha.core.session import Session
        s = Session.__new__(Session)
        return hasattr(s, "__init__")
    all_passed &= _check("Runtime Variables (Session)", _check_runtime)
    
    # ── Runtime Models ───────────────────────────────────
    all_passed &= _check("Research Request Model", lambda: __import__("deployment.runtime.models.research_request") is not None)
    all_passed &= _check("Research Result Model", lambda: __import__("deployment.runtime.models.research_result") is not None)
    all_passed &= _check("Research Statistics Model", lambda: __import__("deployment.runtime.models.research_statistics") is not None)

    # ── Research Controller & Event Bus ──────────────────
    all_passed &= _check("Event Bus", lambda: __import__("deployment.runtime.event_bus") is not None)
    all_passed &= _check("Research Controller", lambda: __import__("deployment.runtime.research_controller") is not None)

    # ── Report Generator ─────────────────────────────────
    all_passed &= _check("Report Generator", lambda: __import__("khabrichacha.tools.builtin.report_generator") is not None)

    # ── Browser / Playwright ─────────────────────────────
    def _check_playwright():
        import playwright  # noqa: F401
        return True
    all_passed &= _check("Playwright", _check_playwright)

    def _check_chromium():
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    # Chromium is optional — don't fail the whole thing
    _check("Chromium Browser", _check_chromium)

    # ── Google Drive ─────────────────────────────────────
    def _check_drive():
        try:
            import google.colab  # noqa: F401
            from pathlib import Path
            return Path("/content/drive/MyDrive").exists()
        except ImportError:
            return True  # Not Colab — skip
    all_passed &= _check("Google Drive (if Colab)", _check_drive)

    # ── Strategy, Retrieval & Intelligence (v1.4, v1.5, v1.6) ──
    all_passed &= _check("Query Classifier (v1.4)", lambda: __import__("deployment.runtime.query_classifier") is not None)
    all_passed &= _check("Retriever (v1.5)", lambda: __import__("deployment.runtime.retrieval.retriever") is not None)
    all_passed &= _check("Deduplicator (v1.5)", lambda: __import__("deployment.runtime.retrieval.deduplicator") is not None)
    all_passed &= _check("Source Ranker (v1.5)", lambda: __import__("deployment.runtime.retrieval.source_ranker") is not None)
    all_passed &= _check("Trust Evaluator (v1.5)", lambda: __import__("deployment.runtime.retrieval.trust_evaluator") is not None)
    all_passed &= _check("Workspace Index (v1.5)", lambda: __import__("deployment.runtime.retrieval.workspace_index") is not None)
    all_passed &= _check("Knowledge Retriever (v1.5)", lambda: __import__("deployment.runtime.retrieval.knowledge_retriever") is not None)
    all_passed &= _check("Structured Extractor (v1.5)", lambda: __import__("deployment.runtime.extraction.structured_extractor") is not None)
    all_passed &= _check("Table Normalizer (v1.5)", lambda: __import__("deployment.runtime.extraction.table_normalizer") is not None)
    all_passed &= _check("Numerical Validator (v1.6)", lambda: __import__("deployment.runtime.intelligence.numerical_validator") is not None)
    all_passed &= _check("Consensus Engine (v1.6)", lambda: __import__("deployment.runtime.intelligence.consensus_engine") is not None)
    all_passed &= _check("Entity Resolver (v1.6)", lambda: __import__("deployment.runtime.intelligence.entity_resolver") is not None)
    all_passed &= _check("Temporal Resolver (v1.6)", lambda: __import__("deployment.runtime.intelligence.temporal_resolver") is not None)
    all_passed &= _check("Context Optimizer (v1.6)", lambda: __import__("deployment.runtime.intelligence.context_optimizer") is not None)
    all_passed &= _check("Query Decomposer (v1.6)", lambda: __import__("deployment.runtime.intelligence.query_decomposer") is not None)
    all_passed &= _check("Knowledge Graph (v1.6)", lambda: __import__("deployment.runtime.intelligence.knowledge_graph") is not None)
    all_passed &= _check("Citation Builder (v1.6)", lambda: __import__("deployment.runtime.intelligence.citation_builder") is not None)
    all_passed &= _check("Tool Selector (v1.6)", lambda: __import__("deployment.runtime.intelligence.tool_selector") is not None)
    all_passed &= _check("Model Selector (v1.6)", lambda: __import__("deployment.runtime.intelligence.model_selector") is not None)
    all_passed &= _check("Failure Recovery (v1.6)", lambda: __import__("deployment.runtime.intelligence.failure_recovery") is not None)
    all_passed &= _check("Response Planner (v1.5)", lambda: __import__("deployment.runtime.response_planner") is not None)
    all_passed &= _check("Advanced Result Builder (v1.5)", lambda: __import__("deployment.runtime.advanced_result_builder") is not None)
    
    # ── Refinements (v1.7) ──
    all_passed &= _check("Answerability Estimator (v1.7)", lambda: __import__("deployment.runtime.intelligence.answerability_estimator") is not None)
    all_passed &= _check("Official Source Resolver (v1.7)", lambda: __import__("deployment.runtime.intelligence.official_source_resolver") is not None)
    all_passed &= _check("Structured Resolver (v1.7)", lambda: __import__("deployment.runtime.intelligence.structured_resolver") is not None)
    all_passed &= _check("Cost Estimator (v1.7)", lambda: __import__("deployment.runtime.intelligence.cost_estimator") is not None)
    all_passed &= _check("Intent Memory (v1.7)", lambda: __import__("deployment.runtime.intelligence.intent_memory") is not None)

    # ── Summary ──────────────────────────────────────────
    print()
    print("=" * 60)
    if all_passed:
        print("  OVERALL: PASS [Y]")
    else:
        print("  OVERALL: FAIL [N]  (see individual results above)")
    print("=" * 60)
    print()

    return all_passed


if __name__ == "__main__":
    run_verification()
