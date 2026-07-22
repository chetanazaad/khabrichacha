# KhabriChacha: Complete Data Flow & Query Flow (with module ownership)

This document describes end-to-end **query flow** (how a user question turns into a strategy + tool calls + evidence) and **data flow** (what data structures are created/modified and by which module).

---

## 0) Diagram legend

- Boxes = modules/functions/files
- Arrows = ownership / control transitions
- Brackets `[...]` = data objects

---

## 1) High-level diagrams

### 1.1 Control-plane (query flow)
```mermaid
flowchart TD
  U[User Question] --> UI[UI (NiceGUI)]
  UI --> RC[ResearchController.start_research()]
  RC --> QC[QueryClassifier.classify()]
  QC -->|strategy| DISPATCH{Strategy Dispatcher}

  DISPATCH --> FAST[_execute_fast()]
  DISPATCH --> LOOKUP[_execute_lookup()]
  DISPATCH --> STRUCTURED[_execute_structured()]
  DISPATCH --> COMPARISON[_execute_comparison()]
  DISPATCH --> ANALYSIS[_execute_analysis()]
  DISPATCH --> RESEARCH[_execute_research()]
  DISPATCH --> DEEP[_execute_deep_research()]

  FAST --> QE[QualityEvaluator.evaluate()]
  LOOKUP --> QE
  STRUCTURED --> QE
  COMPARISON --> QE
  ANALYSIS --> QE
  RESEARCH --> QE
  DEEP --> QE

  QE -->|maybe escalate| DISPATCH

  RC --> EXPORT[ReportExporter.generate()]
  EXPORT --> PM[ProjectManager.save_project()/unlock_project()]
```

### 1.2 Data-plane (what data objects move between modules)
```mermaid
flowchart LR
  REQ[ResearchRequest] --> RC[ResearchController]

  subgraph Retrieval
    KR[KnowledgeRetriever.retrieve_local()]
    R[Retriever.retrieve()]
  end

  RC --> KR
  RC --> R

  KR -->|KnowledgeResult| E1{Reuse?}
  R -->|RetrievalResult| E2{Need fetch?}

  E1 -->|yes reusable_content| FASTEVID[Evidence (local) for answer]
  E2 -->|fetch_page| FETCHED[fetch_page results: {content,url,...}]

  subgraph Extraction/Normalization
    SR[StructuredResolver.resolve()/extract_numeric_consensus()]
    CO[ContextOptimizer.optimize()]
  end

  E2 -->|structured| SR
  E2 -->|context compression| CO

  subgraph Planning+Execution (RESEARCH/DEEP)
    P[Planner.generate_plan()/generate_adaptive_plan()]
    O[Orchestrator.run()] 
    TR[ToolExecutor -> ToolRegistry]
  end

  RC -->|RESEARCH/DEEP| P
  P --> O
  O --> TR

  O --> TOOLOUT[session.runtime[task.id] = tool output]

  RC --> SYN[Strategy synthesis -> direct_answer]
  SYN --> CIT[CitationBuilder]
  SYN --> REPARGS[Report args]
  REPARGS --> EXPORT

  EXPORT --> FILES[report.md/json/pdf/docx + manifest]
```

---

## 2) Query flow (control-plane)


> Notes
> - Some parts of the repo (UI callbacks, specific extractors, fetch/search tools) were not inspected in full during this run; this file focuses on the modules we verified directly in code reads.
> - Strategy names: `FAST`, `LOOKUP`, `STRUCTURED`, `COMPARISON`, `ANALYSIS`, `RESEARCH`, `DEEP_RESEARCH`.

---

## 1) Query flow (control-plane)

### 1.1 Launch / UI → Runtime controller
1. **User starts the app**
   - **Module:** `app.py`
   - **Action:** `start_application()` then `ui.run()` (NiceGUI server)

2. **UI submits a research request** (not fully inspected here, but it drives the runtime)
   - **Runtime entrypoint:** `deployment/runtime/research_controller.py::ResearchController.start_research()`

### 1.2 Strategy selection
3. **Classify mission into a strategy**
   - **Module:** `ResearchController.start_research()`
   - **Calls:** `QueryClassifier().classify(request.mission, request.metadata strategy_override)`
   - **Module:** `deployment/runtime/query_classifier.py::QueryClassifier`
     - Loads rules from `deployment/runtime/strategy_rules.yaml`
     - Computes complexity and applies keyword/regex rules

4. **Validate provider/model availability**
   - **Module:** `ResearchController.start_research()`
   - **Module:** `khabrichacha/llm/manager.py::LLMManager`
     - registers providers (openai, gemini, ollama, transformers, openrouter)

### 1.3 Dispatch to the selected strategy
5. **Strategy dispatch table**
   - **Module:** `ResearchController.start_research()`
   - **Dispatch:**
     - `FAST` → `_execute_fast`
     - `LOOKUP` → `_execute_lookup`
     - `STRUCTURED` → `_execute_structured`
     - `COMPARISON` → `_execute_comparison`
     - `ANALYSIS` → `_execute_analysis`
     - `RESEARCH` → `_execute_research`
     - `DEEP_RESEARCH` → `_execute_deep_research`

### 1.4 Post-answer evaluation + optional escalation
6. **Quality evaluation**
   - **Module:** `ResearchController.start_research()`
   - **Calls:** `QualityEvaluator().evaluate(...)` (not inspected fully)

7. **Escalation if quality too low**
   - **Module:** `ResearchController.start_research()`
   - **Behavior:** if `overall_score < 50.0` and not already escalated:
     - escalates to `RESEARCH` or `DEEP_RESEARCH`

### 1.5 Persistence and export
8. **Persist + export**
   - **Module:** `ResearchController._finalize_and_persist()`
   - **Calls:** `deployment/reporting/report_exporter.py::ReportExporter.generate()`
   - **Module:** `deployment/workspace/project_manager.py::ProjectManager`
     - saves `manifest.json` and report artifacts

---

## 2) Data flow (data-plane)

### 2.1 Request → internal models
**Input:** user supplies a `ResearchRequest` (structure from `deployment/runtime/models/research_request.py`, not inspected fully).

**Created/updated during flow:**
- **Module:** `ResearchController.start_research()`
  - Creates/updates `ResearchResult` and `ResearchStatistics`.
- **Module:** `deployment/runtime/models/research_result.py` (not inspected)

### 2.2 Retrieval result
Retrieval outputs are normalized into a `RetrievalResult`.

- **Module:** `deployment/runtime/retrieval/retriever.py::Retriever.retrieve()`
  - **Creates:** `RetrievalResult` containing:
    - `candidate_sources` (all raw candidates)
    - `ranked_sources` (after ranking)
    - `duplicate_sources` (dedupe duplicates)
    - `filtered_sources` (top relevant sources)
    - `extracted_answer` (optional deterministic answer for FAST/LOOKUP)
    - diagnostic fields

- **Module:** `deployment/runtime/retrieval/knowledge_retriever.py::KnowledgeRetriever.retrieve_local()`
  - **Creates:** `KnowledgeResult`
  - Layers checked:
    - deterministic local knowledge (capitals, simple math)
    - workspace project reuse
    - cached assets reuse
    - returns `needs_web_search` and `reusable_content`

### 2.3 Evidence selection for synthesis
Evidence is assembled by each strategy using fetched content and/or structured extraction.

- **Module:** `deployment/runtime/research_controller.py`
  - Strategy-specific evidence builders (snippets, fetched page content, table output, consensus output).

- **Module:** `khabrichacha/core/orchestrator.py::Orchestrator.run()`
  - Collects per-step tool outputs into:
    - `session.runtime[task.id]`
  - Extracts `all_findings`, `all_sources`
  - Builds `evidence_list` for the final report export

### 2.4 Planning outputs (for RESEARCH/DEEP_RESEARCH)
- **Module:** `khabrichacha/core/planner.py`
  - `generate_plan()` returns `Plan(goal, steps: [PlanStep])`
  - `generate_adaptive_plan()` returns `AdaptivePlan(continue_research, steps: [PlanStep])`

- **Module:** `khabrichacha/core/orchestrator.py`
  - Converts `PlanStep` → runtime task list (`Task` from `khabrichacha/core/state.py`, not inspected)
  - Assigns IDs per iteration: `iter{iteration}_{step.id}`

### 2.5 Tool execution result
Tool execution is abstracted and validated.

- **Module:** `khabrichacha/tools/registry.py::ToolRegistry`
  - Validates `arguments` against tool inputs (`tool.validate(arguments)`)
  - Executes tool via `tool.execute(arguments)`

- **Module:** `deployment/runtime/tool_executor.py::ToolExecutor`
  - Wraps `ToolRegistry` with a middleware pipeline

- **Module:** `khabrichacha/core/orchestrator.py`
  - Runs tools using `execute_tool(tool_name, resolved_args)`

---

## 3) Unified module/data-flow map (by stage)

The following table summarizes **which module owns which input/output**.

| Stage | Responsibility | Primary modules |
|---|---|---|
| UI entry | start server | `app.py`, `khabrichacha/ui/*` |
| Request entry | create session + pick strategy | `ResearchController.start_research()` |
| Strategy classification | compute strategy | `QueryClassifier` |
| Provider/model validation | ensure LLM ready | `LLMManager` |
| Retrieval local reuse | workspace/cache/local knowledge | `KnowledgeRetriever.retrieve_local()` |
| Retrieval web | search, merge, dedupe, rank, filter | `Retriever.retrieve()` |
| Fetch | download page content | `fetch_page` tool via `ToolRegistry` |
| Evidence gates | remove off-topic evidence | `Retriever` and `Orchestrator` and `_is_content_relevant()` |
| Structured extraction | tables + numeric consensus | `StructuredResolver` + `ConsensusEngine` (used via controller) |
| Context compression | reduce prompt context | `ContextOptimizer.optimize()` |
| Planning loop (adaptive) | create tool steps per iteration | `Planner.generate_adaptive_plan()` |
| Tool execution | execute search/fetch/python/report | `ToolExecutor` → `ToolRegistry` |
| Final assembly | synthesize answer + citations | controller strategy methods + `ReportExporter` |
| Persistence | write report files + manifest | `ProjectManager` |

---

## 4) Per-strategy query flow & evidence flow (control + data)

### 4.1 FAST
**Query flow**
1. `ResearchController._execute_fast()`
2. Check `KnowledgeRetriever.retrieve_local()`
3. If no local reusable content → single LLM call

**Evidence/data flow**
- If local reusable content exists:
  - evidence = that content
  - answer = `reusable_content[0]['content']`
- Else:
  - evidence = none (LLM freeform)
  - answer = LLM output string

**Where modules are used**
- Local reuse: `knowledge_retriever.py`
- LLM call: provider from `llm/manager.py`
- Persistence: `_finalize_and_persist()` + `ProjectManager`

---

### 4.2 LOOKUP
**Query flow**
1. `ResearchController._execute_lookup()`
2. Try local reuse: `KnowledgeRetriever.retrieve_local()`
3. If needed → `Retriever.retrieve()`
4. If deterministic extracted answer present:
   - return extracted answer
5. Else:
   - compute evidence sufficiency
   - maybe escalate to ANALYSIS
   - else build prompt from snippets and call LLM

**Evidence/data flow**
- Evidence sources come from:
  - `RetrievalResult.filtered_sources[].snippet`
  - optionally fetched single page text in the “small question fast path” (code path)
- Citations built from `CitationBuilder.build()`

---

### 4.3 STRUCTURED
**Query flow**
1. `ResearchController._execute_structured()`
2. `Retriever.retrieve()` (search only)
3. For top sources → `fetch_page` tool execution
4. Detect structured presence and possibly run `StructuredResolver.resolve()`
5. If not occurrence-count query → numeric consensus extraction
6. If structured docs exist → build response using `AdvancedResultBuilder` + `ResponsePlanner`
7. Else → fallback LLM synthesis on fetched content

**Evidence/data flow**
- Evidence inputs:
  - `fetched_docs[].content`
  - `structured_docs` (tables extracted)
  - `consensus_result.weighted_value` and conflicts
- Citations built from `ret_res.filtered_sources` via `CitationBuilder`

---

### 4.4 COMPARISON
**Query flow**
1. `ResearchController._execute_comparison()`
2. Decompose query: `QueryDecomposer.decompose()`
3. Search/fetch for at least two entities
4. Single LLM call to produce a comparison matrix

**Evidence/data flow**
- Evidence = fetched content snippets per entity
- Output = LLM response + citations

---

### 4.5 ANALYSIS
**Query flow**
1. `ResearchController._execute_analysis()`
2. `Retriever.retrieve()` + fetch top sources
3. Numeric consensus extraction (StructuredResolver) unless occurrence-count query
4. Compress context: `ContextOptimizer.optimize(fetched_text, ...)`
5. Single LLM call using optimized context
6. Append citations

**Evidence/data flow**
- Evidence inputs:
  - `fetched_text` list
  - `optimized_context` string
  - optional `consensus_section`

---

### 4.6 RESEARCH (adaptive off)
**Query flow**
1. `ResearchController._execute_research()`
2. Calls `_run_core_orchestration(enable_adaptive=False)`
3. Project/session setup: `ProjectManager.create_project()`
4. Creates `LLMManager` and `Orchestrator(session, llm_manager, tool_registry)`
5. Calls `Orchestrator.run(mission)`

**Evidence/data flow**
- Orchestrator collects tool outputs per task.
- Builds `all_findings` and `all_sources`.
- Generates final report via `generate_report` tool.

---

### 4.7 DEEP_RESEARCH (adaptive on)
**Query flow**
Same as RESEARCH but with:
- `enable_adaptive=True`
- adaptive plan loop drives multiple iterations of planning + tool execution.

**Evidence/data flow**
- Similar to Orchestrator but may include multiple iterations of evidence gathering.

---

## 5) RESEARCH/DEEP_RESEARCH: Orchestrator’s internal data structures

### 5.1 Iteration runtime map
- **Module:** `khabrichacha/core/session.py` (not inspected)
- **Used by:** `Orchestrator`
- **Map:** `session.runtime[task.id] = raw_result`

### 5.2 Planning steps → tasks
- **Module:** `khabrichacha/core/planner.py` produces `PlanStep` objects.
- **Module:** `khabrichacha/core/orchestrator.py` transforms them into `Task(id=step.id, description=...)`.

### 5.3 Evidence gathering
- **Module:** `Orchestrator.run()`
  - Iterates through completed tasks
  - Parses JSON outputs when possible
  - Builds:
    - `new_findings`: textual evidence snippets
    - `new_sources`: list of `{title, url}`
  - Maintains:
    - `seen_urls` to avoid duplicates
    - `rejected_task_ids` for content rejected by relevance gates

### 5.4 Final report arguments
- **Module:** `Orchestrator.run()`
  - `report_args = {title, objective, findings, sources, evidence?}`
  - `report_tool = tool_registry.get_tool('generate_report')`
  - `report_tool.execute(report_args)`

---

## 6) Quick-reference: Where each key datum comes from

| Datum | Produced by | Used by |
|---|---|---|
| Strategy name | `QueryClassifier.classify()` | `ResearchController` dispatcher |
| Retrieval sources/snippets | `Retriever.retrieve()` | LOOKUP/STRUCTURED/ANALYSIS/COMPARISON |
| Deterministic extracted answer | `Retriever.extract_direct_answer()` | LOOKUP/FAST-style flows |
| Fetched page content | `fetch_page` tool (via ToolRegistry) | STRUCTURED/ANALYSIS/COMPARISON small fast path |
| Table/structured docs | `StructuredResolver.resolve()` | STRUCTURED response builder |
| Numeric consensus | `StructuredResolver.extract_numeric_consensus()` | STRUCTURED/ANALYSIS |
| Context-optimized text | `ContextOptimizer.optimize()` | ANALYSIS LLM prompt |
| Adaptive plan steps | `Planner.generate_adaptive_plan()` | Orchestrator tool execution loop |
| Evidence lists | `Orchestrator.run()` (findings/sources/evidence) | `generate_report` tool and final response |
| Citations | `CitationBuilder` | appended to strategy answers |
| Reports/files | `ReportExporter` + `ProjectManager.save_project()` | UI downloads |

---

## 7) Known gaps (what wasn’t inspected in this run)
- UI callbacks/components that create `ResearchRequest` and set `output_formats`.
- Exact implementations of:
  - `StructuredResolver`, `CitationBuilder`, `AdvancedResultBuilder`, `ContextOptimizer`
  - tool implementations for `search_web/search_news/fetch_page/fetch_pdf/generate_report`

Those can be added in a follow-up if you want a fully exhaustive mapping including every tool’s input/output schema.

