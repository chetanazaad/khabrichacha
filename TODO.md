# TODO — Query Understanding/Verification + Pre-launch Wizard + Nav Wiring

## Part 1 — Query understanding & verification refactor
- [x] Define Stage 1 “Query Understanding” schema (exact JSON fields, answer_type taxonomy, ambiguity flag, confidence).
- [x] Replace/retire `QueryClassifier` regex tiers and `is_occurrence_count_query` usage.
- [x] Implement deterministic routing: map Stage-1 `answer_type` + constraints → existing dispatch (`FAST/LOOKUP/STRUCTURED/COMPARISON/ANALYSIS/RESEARCH/DEEP_RESEARCH`).
- [x] Implement Stage 2 verification algorithm:
  - [x] Traceability: answer claims must map to retrieved evidence (e.g., numeric + key phrases).
  - [x] Satisfaction: answer matches Stage-1 `answer_type` (count/list/comparison/etc.).
  - [x] Decision policy: default rule **B** (non-answer unless confidence + evidence coverage both pass).
  - [x] Escalation path (optional): if policy allows, step up to more thorough strategy.
- [x] Implement honest non-answer format (template for “couldn't confidently determine” with what was found).
- [x] Add/extend unit tests for Stage 1/Stage 2 correctness + routing.

## Part 2 — Pre-launcher UI (wizard)
- [x] Create a new wizard screen before existing UI:
  - [x] Detect system configuration (CPU cores, RAM, GPU presence, OS).
  - [x] Heuristic “cloud/high-resource” detection with user override.
  - [x] Suggest small/large model pair.
- [x] Implement Ollama installation flow:
  - [x] Windows: winget/installer exe path.
  - [x] Mac/Linux: OS-appropriate install script.
  - [x] Show “installing, can take a few minutes” state; stream stdout if possible.
- [x] Implement model install flow:
  - [x] Pull suggested small + large models via `ollama pull ...`.
  - [x] Provide progress UI and error handling.
- [x] Implement Python dependency install flow:
  - [x] Run `pip install -r requirements.txt`.
  - [x] Show progress/errors in UI.
- [x] Launch button hands off to existing research UI.

## Part 3 — Fix left navigation menu
- [x] Identify UI navigation component in `khabrichacha/ui/`.
- [x] Wire PROJECTS / MODELS / SETTINGS / LOGS / ABOUT pages to real handlers.
- [x] Add minimal page implementations if missing.

## Validation
- [x] Run tests: `pytest`.
- [x] Run benchmark scripts under `tests/`.
- [x] Smoke test: UI load → wizard → research answer → persistence downloads.

