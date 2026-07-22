# KhabriChacha — Project Analysis Report

**Version:** 0.1.0
**Python:** >=3.10
**Date:** 2026-07-21

---

## 1. Project Overview

KhabriChacha is an **agentic AI deep-research framework** that takes a user's research question, automatically searches the web, fetches and browses pages (including JavaScript-rendered content via Playwright), reconciles facts across sources, and produces a sourced answer in multiple formats (Markdown, JSON, PDF, Word). It ships with a **NiceGUI-based web UI** and is designed to run **entirely for free** using local LLM models via Ollama, with optional cloud API support (OpenAI, Gemini, OpenRouter, Hugging Face Transformers).

---

## 2. Architecture Summary

The codebase follows a layered architecture with two parallel research pipelines:

```
┌─────────────────────────────────────────────────────────────────┐
│                        UI Layer (NiceGUI)                        │
│  wizard.py → components.py → callbacks.py → pages.py            │
│  Theme / CSS / Real-time progress / Log streaming                │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
┌─────────────────────────┐   ┌──────────────────────────────────┐
│   khabrichacha/core/    │   │    deployment/runtime/            │
│   (Simple Pipeline)     │   │    (Advanced Research Engine)     │
│                         │   │                                  │
│  orchestrator.py        │   │  research_controller.py          │
│  planner.py             │◄──┤  query_classifier.py             │
│  session.py / state.py  │   │  query_understanding.py          │
│  relevance.py           │   │  retrieval/retriever.py          │
│  grounding.py           │   │  intelligence/ (14 modules)      │
│  embeddings.py          │   │  extraction/                     │
└────────┬────────────────┘   └──────────┬───────────────────────┘
         │                                │
         └──────────┬─────────────────────┘
                    ▼
     ┌──────────────────────────────┐
     │     khabrichacha/tools/      │
     │  search_web, search_news,    │
     │  fetch_page, fetch_pdf,      │
     │  python_executor,            │
     │  report_generator            │
     └──────────────────────────────┘
                    │
         ┌──────────┴──────────────┐
         ▼                         ▼
┌──────────────────┐    ┌────────────────────────┐
│  khabrichacha/   │    │   deployment/workspace/ │
│  llm/            │    │   project_manager.py    │
│  (5 providers)   │    │   workspace_manager.py  │
└──────────────────┘    │   cache_manager.py      │
                        └────────────────────────┘
```

---

## 3. Module Breakdown

### 3.1 Entry Point — `app.py`
- Loads configuration, initializes logging, launches NiceGUI server.
- `python app.py` starts the UI at `http://127.0.0.1:8080`.
- Entry point for `khabrichacha` console script via `pyproject.toml`.

### 3.2 Core Engine — `khabrichacha/core/`
| File | Responsibility |
|------|---------------|
| `orchestrator.py` (519 lines) | Multi-iteration adaptive research loop with LLM-driven planning, tool execution, relevance gating, and final report synthesis |
| `planner.py` (551 lines) | LLM-powered plan generation (single-pass + adaptive), fallback heuristic plans, JSON parsing with retry, step validation |
| `session.py` | Session state management (runtime data, research state, config, message history) |
| `state.py` | Task/State Pydantic models |
| `relevance.py` (285 lines) | Dependency-free topical relevance scorer: lexical keyword overlap + optional embedding-based semantic similarity |
| `grounding.py` (103 lines) | Post-hoc numeric claim verification against retrieved evidence |
| `embeddings.py` | Embedding backend integration (Ollama nomic-embed-text, OpenAI, Gemini) |
| `query_shape.py` | Query shape classification (occurrence count detection, etc.) |

### 3.3 Research Engine — `deployment/runtime/`
| File | Responsibility |
|------|---------------|
| `research_controller.py` (~1000+ lines) | Main orchestrator for the advanced pipeline; dispatches to 7 strategy handlers, manages quality evaluation and auto-escalation |
| `query_classifier.py` (245 lines) | 3-tier heuristic classifier: regex patterns → keyword scoring matrices → fallback heuristics; maps queries to 7 strategies |
| `query_understanding.py` | Stage 1 query understanding: intent detection, answer type taxonomy, ambiguity detection |
| `response_planner.py` | Response plan builder for structured output |
| `advanced_result_builder.py` | Builds structured results from plans + content |
| `execution_validator.py` | Validates execution completeness |
| `event_bus.py` | Decoupled event messaging for UI updates |
| `tool_executor.py` / `tool_execution_middleware.py` | Tool execution with middleware hooks |
| `runtime_profiler.py` | Performance profiling for initialization and module timing |

### 3.4 Retrieval Pipeline — `deployment/runtime/retrieval/`
| File | Responsibility |
|------|---------------|
| `retriever.py` (335 lines) | Multi-engine search, deduplication, intent-aware ranking, relevance filtering, parallel execution with retry/fallback |
| `source_ranker.py` | Trust/authority/freshness/popularity scoring |
| `deduplicator.py` | URL + content-based deduplication |
| `knowledge_retriever.py` | Local workspace cache retrieval |
| `trust_evaluator.py` | Domain trust scoring |
| `workspace_index.py` | Workspace-based knowledge indexing |

### 3.5 Intelligence Layer — `deployment/runtime/intelligence/`
| Module | Purpose |
|--------|---------|
| `citation_builder.py` | Source citation generation |
| `confidence_aggregator.py` | Multi-signal confidence scoring |
| `consensus_engine.py` | Cross-source numeric value reconciliation |
| `entity_resolver.py` | Entity normalization and resolution |
| `temporal_resolver.py` | Date/time constraint resolution |
| `context_optimizer.py` | Context window optimization for LLM prompts |
| `query_decomposer.py` | Complex query decomposition into subtasks |
| `tool_selector.py` | Dynamic tool selection based on query |
| `model_selector.py` | Dynamic model selection based on strategy |
| `failure_recovery.py` | Graceful degradation and retry strategies |
| `numerical_validator.py` | Numeric data validation |
| `structured_resolver.py` | HTML/Markdown table extraction and normalization |
| `quality_evaluator.py` | Post-execution quality scoring (5 dimensions) |
| `execution_trace.py` | Execution trace recording for debugging |
| `intent_memory.py` | Intent memory across iterations |
| `official_source_resolver.py` | Official/government source detection |
| `knowledge_graph.py` | Knowledge graph construction |
| `cost_estimator.py` | Cost estimation per query |
| `answerability_estimator.py` | Pre-execution answerability scoring |

### 3.6 Extraction — `deployment/runtime/extraction/`
| Module | Purpose |
|--------|---------|
| `structured_extractor.py` | Structured data extraction from fetched documents |
| `table_normalizer.py` | Table normalization and unification |

### 3.7 LLM Providers — `khabrichacha/llm/`
| Provider | File | Backend |
|----------|------|---------|
| OpenAI | `providers/openai.py` | OpenAI API + OpenRouter (via OpenAI client) |
| Gemini | `providers/gemini.py` | Google Generative AI |
| Ollama | `providers/ollama.py` | Local Ollama server (HTTP REST) |
| Transformers | `providers/transformers.py` | Hugging Face local inference |

- `base.py`: Abstract `BaseLLMProvider` with `model_identifier` property
- `manager.py`: Provider registry, config merging, instantiation

### 3.8 Tools — `khabrichacha/tools/`
| Tool | File | Description |
|------|------|-------------|
| `search_web` | `builtin/search_web.py` | DuckDuckGo + optional SearxNG metasearch |
| `search_news` | `builtin/search_news.py` | News-specific search |
| `fetch_page` | `builtin/fetch_page.py` | Web page fetching (requests + Playwright fallback) |
| `fetch_pdf` | `builtin/fetch_pdf.py` | PDF document fetching and text extraction |
| `python_executor` | `builtin/python_executor.py` | Sandboxed Python code execution |
| `generate_report` | `builtin/report_generator.py` | Report generation (Markdown, PDF, DOCX, JSON) |

- `base.py`: Abstract `BaseTool` with validation, metadata, and streaming support
- `registry.py`: Tool registry with registration, lookup, and execution

### 3.9 Provider Management — `khabrichacha/providers/`
- `provider_manager.py` (296 lines): Auto-discovers and validates all LLM providers, probes health, caches results, selects best model per strategy

### 3.10 UI Layer — `khabrichacha/ui/`
| File | Responsibility |
|------|---------------|
| `main.py` | NiceGUI startup, custom loguru sink for live log streaming |
| `components.py` (246 lines) | Full layout: status bar, left nav, mission panel, progress header, tabbed workspace (Results/References/Downloads/Logs) |
| `callbacks.py` | Research execution callbacks (run/pause/resume/stop/save) |
| `pages.py` | Multi-page navigation (Projects/Models/Settings/Logs/About) |
| `wizard.py` (88 lines) | Pre-launch setup wizard: system detection, Ollama install, model pull, dependency install |
| `theme.py` | Custom CSS for dark theme, status badges, panel styling |
| `ui_state.py` | Global mutable UI state (input refs, labels, indicators) |

### 3.11 Workspace & Persistence — `deployment/workspace/`
| File | Responsibility |
|------|---------------|
| `workspace_manager.py` | Root workspace directory management |
| `project_manager.py` | Project CRUD, manifest management, locking |
| `workspace_schema.py` | Pydantic models for workspace/project/runtime state |
| `cache_manager.py` | Research result caching |
| `asset_manager.py` | Asset (report files) management |

### 3.12 Reporting — `deployment/reporting/`
- `report_exporter.py`: Generates report.md, report.json, report.pdf (via ReportLab), report.docx (via python-docx)

### 3.13 Data Models — `deployment/runtime/models/`
15 Pydantic models covering: `ResearchRequest`, `ResearchResult`, `ResearchStrategy`, `ResearchStatistics`, `RetrievalResult`, `CandidateSource`, `ConsensusResult`, `StructuredDocument`, `TrustEvaluation`, `ErrorInfo`, `ResearchEvent`, `QueryUnderstanding`, `KnowledgeObjects`, `RejectionInfo`.

---

## 4. Research Strategies (7-tier Classification)

The system classifies each query into one of 7 strategies based on complexity scoring and keyword analysis:

| Strategy | Complexity | Search | Fetch | LLM | Planner | Iterations | Est. Latency | Est. Cost |
|----------|-----------|--------|-------|-----|---------|------------|-------------|-----------|
| **FAST** | 0 | No | No | Yes | No | 0 | 2s | Free |
| **LOOKUP** | 1 | Yes | No | No | No | 1 | 5s | Low |
| **STRUCTURED** | 2 | Yes | Yes | No | No | 1 | 8s | Low |
| **COMPARISON** | 3 | Yes | Yes | Yes | No | 1 | 10s | Medium |
| **ANALYSIS** | 3 | Yes | Yes | Yes | No | 1 | 15s | Medium |
| **RESEARCH** | 4 | Yes | Yes | Yes | Yes | 3 | 120s | Medium |
| **DEEP_RESEARCH** | 5 | Yes | Yes | Yes | Yes | 5 | 300s | High |

Auto-escalation: if quality score < 50/100, the system escalates to a higher strategy (one level at a time, max one escalation per request).

---

## 5. Key Design Patterns

1. **Strategy Pattern**: Query classification dispatches to purpose-built pipeline handlers
2. **Adaptive Planning**: LLM generates execution plans; results feed back into next iteration's planning
3. **Relevance Gating**: Two-stage filtering (query-level + source-level) prevents off-topic drift
4. **Grounding Verification**: Post-hoc numeric claim checking against evidence
5. **Quality Evaluation**: 5-dimension scoring (completeness, correctness, citation, structure, relevance) with auto-escalation
6. **Tool Registry**: Extensible tool system with validation, metadata, and registry pattern
7. **Provider Abstraction**: Uniform LLM interface across 5 providers with health probing
8. **Event Bus**: Decoupled event system for UI progress updates
9. **Graceful Degradation**: Fallback plans when LLM is unavailable, retry pipelines for search failures

---

## 6. Dependencies

### Core
- `nicegui>=2.0.0` — Web UI framework
- `uvicorn>=0.28.0` — ASGI server
- `loguru>=0.7.2` — Structured logging
- `pydantic>=2.0.0` — Data validation/models
- `PyYAML>=6.0.1` — Configuration

### LLM Providers
- `openai>=1.12.0` — OpenAI + OpenRouter
- `google-generativeai>=0.4.0` — Gemini

### Web & Scraping
- `ddgs>=9.0.0` — DuckDuckGo search (replaces frozen `duckduckgo-search`)
- `requests>=2.31.0` — HTTP client
- `beautifulsoup4>=4.12.0` — HTML parsing
- `readability-lxml>=0.8.1` — Content extraction
- `playwright>=1.42.0` — Headless browser for JS-rendered pages
- `PyMuPDF>=1.23.0` — PDF text extraction
- `feedparser>=6.0.10` — RSS/Atom feed parsing

### Data & Export
- `pandas>=2.0.0` / `numpy>=1.24.0` — Data processing
- `reportlab>=4.0.0` — PDF generation
- `python-docx>=1.1.0` — Word document generation

### Optional (local LLM)
- `transformers>=4.38.0` / `torch>=2.2.0` — Hugging Face local inference

---

## 7. Test Suite

**Location:** `tests/` (14 test files)

| Test File | Coverage Area |
|-----------|---------------|
| `test_khabrichacha.py` | Core integration tests |
| `test_query_classifier.py` | Query classification correctness |
| `test_query_understanding.py` | Stage 1 query understanding |
| `test_execution_intelligence.py` | Intelligence layer modules |
| `test_strategy_validation.py` | Strategy budget/config validation |
| `test_search_diagnostics.py` | Search pipeline diagnostics |
| `test_regression.py` | Regression test suite |
| `test_benchmark_entrypoints.py` | Entry point benchmarks |
| `test_ui_wizard.py` | Setup wizard tests |
| `conftest.py` | Shared fixtures |
| `benchmark_performance.py` / `performance_benchmark.py` | Performance benchmarking |

---

## 8. Configuration

### `config.yaml` (root)
```yaml
application:
  name: KhabriChacha
  version: 0.1
storage:
  project_directory: ./projects
logging:
  directory: ./logs
llm:
  provider: none
  model: none
research:
  depth: standard
  max_sources: 25
ui:
  theme: dark
```

### `deployment/runtime/strategy_rules.yaml`
Defines all 7 strategy configurations (budgets, tools, gates) and classification keyword patterns.

### `deployment/base_config.yaml`, `local.yaml`, `docker.yaml`, `colab.yaml`
Environment-specific deployment configurations.

---

## 9. File Statistics

| Category | Count |
|----------|-------|
| Python source files | 125 |
| Test files | 14 |
| YAML config files | 6 |
| Markdown docs | 6 |
| **Total source lines (approx)** | **~8,000+** |

### Source Distribution
- `deployment/runtime/` — ~50 files (largest subsystem)
- `khabrichacha/` — ~40 files (core + UI + tools + LLM)
- `tests/` — 14 files
- `deployment/workspace/` — 5 files
- `deployment/reporting/` — 1 file

---

## 10. Strengths

1. **Zero-cost local operation** — Full functionality with Ollama, no API key required
2. **Multi-strategy adaptive routing** — Automatically matches query complexity to appropriate pipeline
3. **Robust relevance gating** — Two-stage filtering (query + source level) prevents off-topic drift
4. **Grounding verification** — Detects hallucinated numeric claims in synthesized answers
5. **Quality auto-escalation** — Automatically retries with heavier strategies when quality is low
6. **Extensible tool system** — New tools can be added via `BaseTool` + registry
7. **Multi-format export** — PDF, DOCX, Markdown, JSON output
8. **Rich UI** — Real-time progress, live logs, strategy indicators, download management
9. **Search resilience** — Multi-engine fallback (DuckDuckGo → HTML fallback → News → Official sources)
10. **Provider health probing** — Auto-detects available models with caching

---

## 11. Areas for Improvement

1. **Dual pipeline complexity** — `khabrichacha/core/orchestrator.py` and `deployment/runtime/research_controller.py` implement overlapping logic; consolidation would reduce maintenance burden
2. **Planner frame introspection** — `planner.py:_get_tool_registry()` uses `sys._getframe()` to walk the call stack — fragile; should use explicit dependency injection
3. **Missing `__init__.py` files** — Several `deployment/` subdirectories lack `__init__.py`, relying on implicit namespace packages
4. **Test coverage gaps** — No tests for LLM providers, tools, workspace management, or the reporting pipeline
5. **No CI/CD configuration** — No GitHub Actions, pre-commit hooks, or automated test pipeline
6. **UI state management** — Global mutable state in `ui_state.py` is not thread-safe for concurrent users
7. **Hardcoded model catalogs** — `provider_manager.py` has hardcoded model lists instead of dynamic API queries
8. **No Docker/deployment configs** — `deployment/*.yaml` files exist but no `Dockerfile` or `docker-compose.yml`

---

## 12. Data Flow Summary

```
User Query
    │
    ▼
QueryClassifier.classify()  ──►  ResearchStrategy
    │
    ▼
ResearchController.start_research()
    │
    ├──► [FAST]      → LLM direct reasoning
    ├──► [LOOKUP]    → Search → Rank → LLM synthesis
    ├──► [STRUCTURED]→ Search → Fetch → Table extraction → Numeric consensus
    ├──► [COMPARISON]→ Parallel search → Comparison matrix
    ├──► [ANALYSIS]  → Search → Fetch → LLM reasoning
    ├──► [RESEARCH]  → Planner → Multi-iteration adaptive loop
    └──► [DEEP_RESEARCH] → Planner → Extended adaptive loop (5 iterations)
    │
    ▼
QualityEvaluator.evaluate()
    │
    ├──► score >= 50  →  Report Export (MD/JSON/PDF/DOCX)
    └──► score < 50   →  Auto-escalate to higher strategy (max 1 hop)
    │
    ▼
_finalize_and_persist()  →  Project save + manifest update
```

---

*Report generated by codebase analysis on 2026-07-21.*
