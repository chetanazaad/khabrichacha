# KhabriChacha — Technical Audit & Fix Plan

*Prepared for internal use. Kept isolated from any public search/exposure, as requested — this review is based solely on the code inside the uploaded zip.*

## How this was done
I unzipped and read essentially every module (`khabrichacha/`, `deployment/`, `tests/`, configs, docs), traced every import path, and cross‑checked the two engines against each other and against the docs. Where a claim could be independently verified (e.g. the `.gitignore` bug, the `duckduckgo-search` package status), I actually tested it rather than guessing. Line numbers refer to the files as they exist in your zip today.

## The real architecture (this isn't in your README yet)
You actually have **two orchestration engines**, not one:

1. **`khabrichacha/core/`** — the simple engine (`Orchestrator` + `Planner`). LLM plans steps → tools execute → report assembled. This is the only thing your current `README.md` describes.
2. **`deployment/runtime/`** — a much larger "strategy router" (`ResearchController`, `QueryClassifier`, `Retriever`, `TrustEvaluator`, `ConsensusEngine`, `KnowledgeGraph`, etc.). It classifies each query into one of **FAST / LOOKUP / STRUCTURED / COMPARISON / ANALYSIS / RESEARCH / DEEP_RESEARCH** and runs a different, purpose‑built pipeline for each. This is what your UI actually calls (`khabrichacha/ui/callbacks.py` → `ResearchController`). The `RESEARCH` and `DEEP_RESEARCH` strategies internally re‑use engine #1.

This is a genuinely sophisticated design — more advanced than the README lets on. The problem is that it currently **cannot run at all**, for one very specific, very fixable reason. Everything below is ordered so that fixing item 1 is what lets you even start testing the rest.

---

## P0 — Blocking: nothing runs, for anyone, on any machine

### Issue 1: `.gitignore` is silently deleting a whole package your app depends on

**Evidence:** `.gitignore` line 53:
```
workspace/
```
This pattern is **unanchored**, so Git ignores *any* directory named `workspace` at *any* depth — not just the runtime data folder your config points at (`workspace.root: "./workspace"`), but also the source package **`deployment/workspace/`**. I verified this directly (not just by reading): reproducing your `.gitignore` in a scratch repo and running `git check-ignore -v deployment/workspace/workspace_manager.py` confirms it's ignored, matched by exactly that rule.

The result: `deployment/workspace/` — which must contain at least `workspace_manager.py` (`WorkspaceManager`), `project_manager.py` (`ProjectManager`), `workspace_schema.py` (`RuntimeState`, `ResearchState`, `PlannerState`, `ReferenceIndex`, `ReferenceEntry`), plus `asset_manager.py` and `cache_manager.py` (both explicitly checked for in `deployment/verify_environment.py` lines 68–72) — **does not exist anywhere in this zip.** It was never committed.

This isn't a minor missing file. It's imported **at module load time** (not lazily, not in a try/except) in:
- `khabrichacha/ui/callbacks.py` (line 7) — imported the moment the UI module loads
- `khabrichacha/ui/components.py` (line 27)
- `deployment/runtime/research_controller.py` (lines 23 and 31) — the file every strategy in your app runs through
- `deployment/launchers/launch_colab.py` (line 48)
- Every single file in `tests/`

**Net effect:** `python app.py` raises `ModuleNotFoundError: No module named 'deployment.workspace'` before a single UI element is drawn. `pytest` fails to even collect the test suite. The Colab launcher fails identically. This is why, if you've tried "install from git and run it," it simply hasn't worked — it can't, yet.

**Proposed fix (free, no external services needed):**
1. Change the `.gitignore` rule from `workspace/` to `/workspace/` (anchored to the repo root). That excludes only the runtime data folder (which is what `deployment/local.yaml` / `colab.yaml` / `docker.yaml` point `workspace.root` at) and stops shadowing the source package.
2. Recover or rewrite `deployment/workspace/`. First check whether your editor/IDE has local history, or whether an untracked copy still sits on the machine you developed this on (`git status` would have shown it as "untracked," not deleted — so it may well still be sitting on disk, just never `git add`ed). If it's genuinely gone, it needs to be rewritten from the call sites, which is a real but bounded task — `research_controller.py` alone tells you the required surface: `WorkspaceManager(root_path)` with `.root`, `.temp`, `.projects` (path-like, support `/` joins) and `.get_project_path(id)`; `ProjectManager(workspace_manager)` with `.create_project(...)`, `.resume_project(id)`, `.list_projects()`, `.is_locked(id)`, `.promote_session_to_project(id)`, `.load_references()`; plus the `workspace_schema` dataclasses/pydantic models it imports. I'd suggest treating this as its own follow‑up task rather than folding it into this audit — happy to help write it once you're ready.
3. Add a cheap regression guard so this class of bug can't silently return: a CI step (GitHub Actions is free for public repos) that does a **fresh `git clone`** into a clean directory and runs `python -c "import khabrichacha.ui.callbacks"` plus `pytest --collect-only`. Testing against your working directory would never have caught this, because the file was still sitting there, just untracked.

---

## P1 — Your actual main goal: a real browsing agent that hands back structured, aggregated results

You clarified this is the real point of the project — something that can be asked *"find the total number of aviation accidents worldwide"* and come back with a structured, sourced answer, using something closer to an agent that browses than a one-shot search. I went back through the retrieval/extraction/intelligence layers specifically to check whether this already works. Short version: **the pieces that would make this work are mostly already designed and partially built — some of the best code in the repo is sitting here unused — but nothing currently connects them, and the one pipeline built for this bypasses them.** Here's exactly what I found, tracing your own example query through the system.

### Issue A: There is no real "browser agent" — only static, one-shot HTTP fetching

`khabrichacha/tools/builtin/fetch_page.py` does a plain `requests.get()` + BeautifulSoup/`readability-lxml` extraction. `fetch_pdf.py` uses PyMuPDF on a downloaded file. Neither executes JavaScript, clicks anything, scrolls, paginates, or follows a link mid-task based on what it finds. `search_web.py` is a single keyword query to DuckDuckGo; `search_news.py` is a single Google News RSS fetch. All of it is "ask once, read the static HTML once" — not browsing.

You already have the one dependency that would make real browsing possible: **Playwright + headless Chromium is installed and verified by `colab_utils.py`, `deployment/launchers/install_colab.py`, and `deployment/verify_environment.py`** — but as flagged in the earlier packaging section, it is never imported by a single tool. Right now you're paying the install cost (several minutes on Colab) for a browsing capability that doesn't exist yet.

**Proposed fix:** add a Playwright-backed fetch path — used either always, or as a fallback when the static fetch returns too little text (a good trigger: content under ~500 characters, or the page is dominated by `<script>`/loading-skeleton markup) — this is what actually lets you read JS-rendered dashboards, interactive stats pages, and modern news sites that static scraping can't see. This alone is a meaningful, free upgrade from "scraper" to "browser."

### Issue B: "Agent-compatible" browsing means the LLM can decide where to go next — today it can't

Right now every strategy does a fixed shape: search once → fetch top-N in a `for` loop → one LLM call. There's no tool contract that lets the planner say "that page didn't have the number, let me open the link about ICAO's 2024 safety report instead." Your `khabrichacha/core/planner.py` *does* already support multi-step adaptive plans (used by RESEARCH/DEEP_RESEARCH) — that's the right foundation. What's missing is a browsing tool built for that loop: something like `browse(url) -> {text, tables, links}` that returns enough structure (especially outbound links) for the planner to choose a next hop, bounded by the `max_fetches` budget you already track per-strategy. That's a small, concrete addition on top of infrastructure you already have, not a rebuild.

### Issue C: I traced your exact example query through the classifier — it doesn't land where you'd expect

Feeding `"find the total accident happend world wide in aviation flight"` (your phrasing) through `QueryClassifier.classify()` (`deployment/runtime/query_classifier.py`) and `strategy_rules.yaml`:
- No `fast_patterns` or `lookup_keywords` match.
- `structured_keywords` (`budget`, `gdp`, `population`, `election results`, `financial statement`, `statistics`, `data`, `table`, `figures`, `annual report`) — **none of these appear in the query**, so it scores 0 for STRUCTURED, and 0 for every other bucket too.
- It falls through to the word-count fallback (`query_classifier.py` lines 161–174): 9 words → **classified as `ANALYSIS`**, not `STRUCTURED`.

That matters a lot, because `ANALYSIS` (`_execute_analysis`, line 708) does search → fetch → **one single LLM synthesis call** — it never touches `StructuredResolver`, `NumericalValidator`, or `ConsensusEngine` at all. So even in a world with zero bugs, your own example — asked exactly the way you asked it — would come back as a prose paragraph with one number the LLM happened to pick out of its context window, not a structured, cross-checked answer. The keyword lists are just too narrow for how people actually phrase aggregation questions ("total X worldwide," "how many X have there been," "total number of X").

**Proposed fix:** broaden `structured_keywords` in `strategy_rules.yaml` with aggregation phrasing (`"total number of"`, `"how many"`, `"cumulative"`, `"worldwide"`, `"to date"`), and/or — more robust long-term — replace the brittle keyword-matching tier with one cheap LLM classification call (still free on Ollama or a free-tier API) that outputs a strategy name directly. String-matching will always be one rephrasing away from misrouting.

### Issue D: Even when STRUCTURED *is* reached, it can't finish — and it wouldn't give you what you want anyway

Two separate problems here, and they compound:

**D1 — It crashes.** I covered this in the P0 section from a different angle, but it's worth restating here because it's specifically your structured-output pipeline: `_execute_structured` (`research_controller.py` line 512) calls `pm.save_project(...)` at line 622 and reads `manifest.project_id` — but `pm`/`manifest` are only ever created *locally inside* `_setup_session` (line 268), and only on the branch taken for `RESEARCH`/`DEEP_RESEARCH` projects. For `STRUCTURED`, `_setup_session` takes the **temporary-session** branch instead (line 275), which never defines `pm` at all. So `_execute_structured` unconditionally raises `NameError: name 'pm' is not defined` at its last line, every time. Separately, `_execute_lookup`'s low-evidence escalation path (line 470) calls `classifier.classify(...)`, but `classifier` is a local variable inside `start_research()` (line 159) — a different method — so that also raises a `NameError` whenever a LOOKUP query's evidence looks too thin (a very plausible outcome for a sparse-snippet factual query like yours). Both exceptions are caught by a bare `except Exception` in `start_research()` (line 263) that sets `result.success = False` **without populating `result.errors`**, so `khabrichacha/ui/callbacks.py`'s `"\n".join([e.message for e in result.errors])` produces an empty string — the UI just says "Research failed" with no reason at all. You've likely been hitting this blind wall already.

**D2 — Even bug-free, it doesn't aggregate across sources.** This is the more important finding. Walking through `_execute_structured`'s "happy path" (`deployment/runtime/intelligence/structured_resolver.py`):
- `StructuredResolver.resolve()` runs `StructuredExtractor` on each fetched page looking for an actual HTML/markdown `<table>`, and `NumericalValidator` only checks *internal* consistency of one such table (do the rows sum to the stated total, do percentages add to 100%) — it never compares one source's numbers against another's.
- `build_unified_table()` (line 42) then does this: *"For now, we take the largest ... table"* — literally, if 5 sources are fetched and only 2 have an HTML table, it keeps whichever one has more rows and **silently discards everything else**, including any numeric claim written in ordinary prose ("As of 2023, there have been approximately X accidents...") rather than a `<table>` tag.
- The component that's actually designed to solve your exact problem — `deployment/runtime/intelligence/consensus_engine.py`'s `ConsensusEngine.verify_numerical()` — takes a claim plus a list of `{source, value, weight}` and returns a majority/trust-weighted resolution, a confidence score, and an explicit list of agreeing vs. conflicting sources. It's genuinely well-built. **It is imported in `research_controller.py` (line 42) and never instantiated or called anywhere in the entire codebase.** It's dead code sitting right next to the problem it was built to solve.

This is the single highest-leverage fix available to you: **wire `ConsensusEngine` into the STRUCTURED path.** Concretely — after fetching N sources, run `ConsensusEngine.extract_and_verify(claim, docs, regex_pattern)` (already written, already handles trust-weighting via each source's `trust_score`) or a small LLM-assisted extraction step per source to pull out "the number and its stated scope/date," feed all of them in, and present the `ConsensusResult` — majority value, confidence, and the conflicting sources — as your structured answer, instead of quietly keeping one lucky table and throwing the rest away.

### Issue E: Authoritative domains for a given topic aren't recognized, so ranking can't reliably surface them

`deployment/runtime/retrieval/source_ranker.py` + `domain_profiles.yaml` is a genuinely solid multi-factor ranker (authority, trust, freshness, popularity, keyword match — all real, all working). But its domain list only covers generic categories: `.gov`/`.edu` suffixes, a handful of named research sites (arXiv, Nature, IEEE...), Wikipedia, a handful of big news outlets, and a few big tech companies. For your aviation example, the domain that actually matters most — Aviation Safety Network (`aviation-safety.net`) — isn't in the list at all and falls back to a neutral "general" trust score of 50, the same tier as a random blog. (`icao.int` and other `.int` international-body domains have the same problem — no boost.)

**Proposed fix:** this is a cheap, config-only fix — no code changes needed. Add more categories to `domain_profiles.yaml` (an `.int` pattern for international bodies; a topical "official_statistics" category you can extend per-domain: `aviation-safety.net`, `ntsb.gov` — already covered generically by `.gov` — `iata.org`, `faa.gov`, etc.). Longer-term, since you already have `OfficialSourceResolver` generating enhanced queries, give it (or a new small config file) a per-topic list of "known-good" domains so authoritative topical sources get surfaced and boosted automatically for statistical/factual queries, not just generically-trusted TLDs.

### Issue F: One more small code-quality flag while I was in this file

`deployment/runtime/retrieval/retriever.py` has **two** `def retrieve(self, ...)` methods defined in the same `Retriever` class (lines 20 and 99). The first is an incomplete draft that stops mid-function with no return statement; Python simply uses the second, complete definition, so nothing breaks today — but it's a sign of an unfinished edit left in place, and worth deleting so a future refactor doesn't silently start calling the wrong (broken) version.

### What "done" looks like for your aviation-accidents example

Once A–F above are addressed, a query like yours should reasonably produce something like:

| Metric | Value | Scope / Period | Source | Agreement |
|---|---|---|---|---|
| Total accidents (all civil aviation, cumulative) | ~X,XXX | 1919–2024 | Aviation Safety Network | 3/4 sources agree |
| Fatal accidents (scheduled commercial only) | ~XXX | 2000–2024 | ICAO Safety Report | High confidence |

...with a short note explaining *why* sources disagree (different definitions of "accident" vs. "incident," different aircraft categories, different time windows) rather than silently picking one source's number and presenting it as THE answer — that honesty about disagreement is itself part of "structured," and it's exactly what `ConsensusEngine` was built to surface.

---

## P2 — Undermines your core goal: "use free/local LLMs reliably"

### Issue 2: The local Hugging Face provider is unconditionally broken (same bug copy‑pasted 7×)

Across `deployment/runtime/research_controller.py` (lines ~333, ~419, ~489, ~605, ~682, ~752, ~838) the exact same "model verification" snippet appears after every provider instantiation:
```python
actual_model = getattr(provider_obj, "model", None) or getattr(provider_obj, "model_name", None)
if actual_model != request.model:
    raise ValueError(f"Model mismatch: requested '{request.model}', but provider instantiated '{actual_model}'")
```
`OpenAIProvider` and `OllamaProvider` expose `.model`; `GeminiProvider` exposes `.model_name`. But `TransformersProvider` (`khabrichacha/llm/providers/transformers.py`) stores its model under **`.model_id`** — neither name the check looks for. So `actual_model` is always `None`, `None != request.model` is always `True`, and **every single request routed through the transformers provider raises a spurious "Model mismatch" error and fails**, regardless of strategy (FAST, LOOKUP, RESEARCH, all of them hit this check). Given "local/offline HF model" is presumably your main *zero‑cost, no‑API‑key* path, this quietly breaks the entire point of offering it.

**Proposed fix:** don't special-case attribute names at all. Add one required property to `BaseLLMProvider` (`khabrichacha/llm/base.py`), e.g. `model_identifier`, implement it in all four providers (`TransformersProvider.model_identifier -> self.model_id`), and replace all 7 copy‑pasted blocks with a single helper method on `ResearchController`, e.g. `self._get_verified_provider(provider_name, model_name)`. One fix, one place, can't drift out of sync again.

### Issue 3: Ollama requests use a fixed 30‑second timeout

`khabrichacha/llm/providers/ollama.py` hard-codes `timeout=30` on every `requests.post(...)` call. Local CPU inference for the kind of long, structured JSON planning prompts this app sends (see `planner.py`'s `_build_prompt` / `generate_adaptive_plan`) routinely takes well over 30 seconds on a laptop or a free Colab CPU runtime. Whenever that happens the code falls into `except Exception` and returns a fake `"[Mock Ollama ...]"` string *as if it were a real model response* — which then fails to parse as JSON downstream and silently falls back to the (weaker) heuristic planner, with no clear error surfaced to the user about what actually happened.

**Proposed fix:** make the timeout configurable (`config.get("timeout", 120)` or higher), and — more importantly — stop returning a fake mock string on failure. Raise the real exception (or a clearly-labeled error string like `"[OLLAMA_TIMEOUT]"`) so callers can distinguish "the model answered with fallback text" from "the request failed," instead of quietly masquerading a timeout as a real (garbled) response.

### Issue 4: The default local model is a large, gated model — bad first-run experience

`TransformersProvider` defaults to `meta-llama/Meta-Llama-3-8B-Instruct` on `device="cpu"` with `torch.float32`. That model is (a) gated on Hugging Face — it requires accepting Meta's license and an auth token before it will even download, and (b) an 8B‑parameter model in fp32 on CPU, which is impractically slow for anyone just trying the project for free with no GPU. For a "clone and run" free experience, the default should be something small, ungated, and CPU‑friendly.

**Proposed fix:** default to a small, license-open model (something in the 1–3B class that runs acceptably on CPU) or — better, since you already support it — make **Ollama** the default "free local" path instead of Transformers, since Ollama models are pulled as pre-quantized GGUF files and run far better on CPU out of the box. Keep Transformers as an opt-in for people who specifically want it, with a clear README note about gated models needing `huggingface-cli login`.

### Issue 5: "OpenRouter" is offered in the UI but doesn't actually work

`khabrichacha/providers/provider_manager.py` probes for `OPENROUTER_API_KEY` and, if present, lists models like `openrouter/anthropic/claude-3.5-sonnet` as selectable in the UI dropdown (`_get_model_options()` in `ui/components.py`). But `khabrichacha/llm/manager.py`'s `_register_default_providers()` only ever registers `openai`, `gemini`, `ollama`, `transformers` — there is **no `OpenRouterProvider` class anywhere in the codebase.** Selecting it crashes with `ValueError: LLM Provider 'openrouter' is not registered.`

**Proposed fix (small, since OpenRouter speaks the OpenAI API dialect):** add an optional `base_url` parameter to `OpenAIProvider.__init__` (currently hard-coded to the default OpenAI endpoint), and register a thin `OpenRouterProvider(OpenAIProvider)` subclass that reads `OPENROUTER_API_KEY` and sets `base_url="https://openrouter.ai/api/v1"`. This is genuinely useful for your "free" angle too — OpenRouter has several free-tier models. Until this is done, remove `"openrouter"` from `provider_manager.py`'s discovery so the UI doesn't offer a button that's guaranteed to crash.

### Issue 6: Your only key‑free web search backend is on a deprecated, frozen package

`requirements.txt` pins `duckduckgo-search>=6.0.0`, which `search_web.py` imports as `from duckduckgo_search import DDGS`. I checked: **that package was frozen by its maintainer in July 2025 and renamed to `ddgs`** — the old name no longer receives fixes for DuckDuckGo's anti-bot changes, meaning search quietly degrades over time even though the install never errors. The new package (`pip install ddgs`) is a drop-in replacement — same `DDGS` class, same `.text(query, max_results=...)` signature, same result shape (`title`/`href`/`body`).

**Proposed fix:** switch `requirements.txt` and the import in `search_web.py` to `ddgs` (with a `try: from ddgs import DDGS / except ImportError: from duckduckgo_search import DDGS` fallback if you want backward compatibility for existing installs).

### Issue 7: README tells users to put API keys in `config.yaml` — that file is never read

The top-level `config.yaml` (`llm: {provider: none, model: none}`, no `providers` section at all) is **not** what actually gets loaded. The real config path is `deployment/config_loader.py`, which reads `deployment/base_config.yaml` + an environment override (`local.yaml` / `colab.yaml` / `docker.yaml`) and validates it through a Pydantic model (`KhabriChachaConfig`) that has **no `providers` or `api_key` field at all**. `ProviderManager._probe_openai()` etc. only ever find keys via `os.environ.get("OPENAI_API_KEY")` and friends. So the README's "Add your api keys inside `config.yaml`" instruction is simply incorrect for how the app actually behaves today.

**Proposed fix:** either (a) add a `providers: {openai: {api_key: ...}, ...}` section to the real `KhabriChachaConfig` model and read it in `ProviderManager`, so YAML‑based keys genuinely work, or (b) — simpler, and arguably better for a project you're giving away for free (nobody should commit API keys to a config file they might accidentally push) — update the README to clearly say "set these as environment variables" and drop the config.yaml instruction entirely. A `.env.example` file listing `OPENAI_API_KEY=`, `GEMINI_API_KEY=`, `OPENROUTER_API_KEY=` (all optional; Ollama/Transformers need none) would make the "which keys do I actually need" question obvious at a glance.

---

## P3 — Undermines your stated UX goal: "see progress, get output as PDF"

### Issue 8: PDF generation can silently fail on completely ordinary scraped text

`deployment/reporting/report_exporter.py` builds the PDF with ReportLab's `Paragraph(text, style)` for findings, evidence, and timeline text pulled straight from web-scraped content and LLM output — **without XML-escaping it** (no `xml.sax.saxutils.escape()` anywhere). ReportLab's `Paragraph` parses its input as a small XML-like markup language, so any finding containing a literal `<`, `>`, `&`, or a stray `<tag>`-looking substring (extremely common in scraped article text) raises a parse error inside `_build_pdf`. That exception is caught by the outer `try/except` in `ReportExporter.generate()`, so the failure is **silent** — the user just doesn't get a PDF, with nothing more than a log line explaining why.

**Proposed fix:** wrap every user-derived string going into `Paragraph()` with `xml.sax.saxutils.escape()` before formatting (careful to still allow your own intentional `<b>`/`<br/>` tags, so escape the *content* before you interpolate it, not the whole assembled string).

### Issue 9: There's no way to actually download the report from the UI — and Word/.docx isn't generated at all

`khabrichacha/ui/components.py`'s "Downloads" tab (`_build_tabbed_workspace`) is a hard-coded placeholder:
```python
ui.markdown("_No downloads available._").classes("results-panel text-sm")
```
There is no logic behind it at all — no button, no file link, nothing wired to `result.project_path` or the files `ReportExporter` actually produces. Given your stated goal is explicitly "get the output as PDF, doc, text, or whatever is suitable," this tab is the one piece of UI that most directly matters, and it currently does nothing.

It's also worth being precise about what `ReportExporter.generate()` (`deployment/reporting/report_exporter.py`, line 43) actually produces today, since you specifically asked for PDF **and** Word (.doc/.docx) **and** text: it returns exactly three things — `report_md` (Markdown — this already covers your "text" request reasonably well, it's plain-text-readable), `report_json` (structured data, not really an end-user download), and `report_pdf_bytes` (via ReportLab, when installed). **There is no `.docx`/Word generation anywhere in the codebase, and `python-docx` isn't a dependency** — so "doc" specifically is a real gap, not just a UI wiring gap.

**Proposed fix (free, small addition):**
1. Add `python-docx` (MIT-licensed, free) to `requirements.txt`, and a `_build_docx()` method alongside the existing `_build_markdown()`/`_build_pdf()` in `ReportExporter` — it's a similar shape of work to the PDF builder (iterate the same `findings`/`sources`/`evidence`/`timeline` data into `Document()` paragraphs/headings/tables instead of ReportLab flowables), returning `report_docx_bytes` from `generate()` alongside the other three.
2. Save all four artifacts to the project folder when a run completes (`report.md`, `report.json`, `report.pdf`, `report.docx`) — this depends on `deployment/workspace/` existing again (Issue 1) and `ProjectManager.save_project(...)` actually persisting them.
3. Wire the Downloads tab for real: once files exist at `result.project_path`, populate that tab with one `ui.download()` button per available format (NiceGUI supports this directly) instead of the current hard-coded "No downloads available" text. Show only the formats that actually exist for a given run (e.g. a FAST/LOOKUP answer might reasonably only offer `.md`/`.txt`, while RESEARCH/DEEP_RESEARCH/STRUCTURED offer all four).

This is a small, well-contained addition once Issue 1 (workspace) is fixed — the report *content* is already being assembled correctly; it just needs one more format and a UI that actually exposes what's already being generated.


### Issue 10: The progress bar is fake, and Pause/Resume/Stop don't do anything

In `khabrichacha/ui/callbacks.py`, `run_research()` sets `ui_state.progress_bar.set_value(0.5)` with the comment `# Indeterminate for now`, then `1.0` on completion — it never reflects real step/iteration progress, even though the `EventBus` *is* already wired to push textual log/status updates during the run (that part works). Separately, `pause_research()`, `resume_research()`, and `stop_research()` (same file) each just call `logger.info(...)` — clicking "Stop" while a research mission is running does **not** cancel it; `run.io_bound(_research_controller.start_research, request)` keeps executing in the background regardless.

**Proposed fix:** drive `progress_bar` off real counters you already compute (e.g. current iteration / `strategy.max_iterations` for RESEARCH/DEEP_RESEARCH, or a step counter from `ExecutionTraceRecorder`) via the existing `EventBus` subscription rather than a hard-coded value. For Stop, thread a cancellation token (e.g. a simple `threading.Event`) through `ResearchController.start_research` that gets checked between tool calls/iterations — full preemption of a running LLM call isn't realistic, but stopping "after the current step" is a reasonable, honest version of "Stop." At minimum, relabel the buttons or disable them until they're real, so the UI doesn't promise something it can't deliver.

### Issue 11: The no-LLM / LLM-failure fallback planner fetches hardcoded junk URLs

In `khabrichacha/core/planner.py`, `_build_fallback_plan()` — which runs whenever no LLM manager is configured, or the LLM planning call throws — hardcodes:
```python
args={"url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
```
for the "fetch the PDF" step, and `args={"url": "https://example.com"}` for "fetch content from search results" — instead of using the URLs actually returned by the preceding search step. `_build_adaptive_fallback()` has the same issue with `"${step1[*].url}"` templating that only gets resolved by the orchestrator's variable-resolution pass — worth double-checking end-to-end, since a hardcoded W3C dummy PDF and `example.com` in the *other* fallback path suggests this substitution wasn't consistently applied everywhere.

**Proposed fix:** make every fallback "fetch" step depend on and reference the prior search step's output (the `${step1[*].url}` pattern already used correctly elsewhere in the same file) instead of literal placeholder URLs, so degraded/offline mode still does something useful rather than fetching an unrelated dummy file.

---

## P4 — Security & robustness (matter more once this is shared beyond just you)

### Issue 12: `python_executor`'s "sandbox" isn't a real security boundary

`khabrichacha/tools/builtin/python_executor.py` runs LLM‑authored code via `exec()` with a restricted `__builtins__` dict and a custom `__import__` allow‑list. This is a well-known-weak isolation pattern — Python's own object model (attribute introspection through base classes, etc.) gives a determined actor ways to reach outside a builtins allow-list of this shape, even without `__import__`. Since the code being executed here is generated by an LLM plan — and that plan's *content* can be influenced by whatever text got fetched from the web (a classic prompt-injection vector: a scraped page could contain text designed to steer the planner into writing code that helps escape) — this is worth taking seriously, not as an abstract concern but as a concrete gap between "looks sandboxed" and "is sandboxed."

**Proposed fix (free options, in increasing order of effort):** (a) simplest — run it in a genuinely separate OS process with `subprocess` and a hard wall-clock/memory limit (`resource.setrlimit` on Linux) rather than in-process `exec()`; (b) better — run it inside a lightweight container (Docker, which you likely already want for the `docker.yaml` deployment target anyway) with no network access and a read-only filesystem; (c) if you want to stay in-process, use a maintained sandboxing library rather than a hand-rolled builtins allow-list. Given this project is meant to be shared/self-hosted by other people, I'd treat this as a "before wider release" item rather than something to ship as-is.

### Issue 13: UI/controller state is global, not per-user

`khabrichacha/ui/ui_state.py` stores every widget reference (`progress_bar`, `results_markdown`, etc.) as **module-level globals**, and `khabrichacha/ui/callbacks.py` similarly instantiates `_research_controller`, `_workspace_manager`, `_provider_manager`, `_event_bus` once, at import time, as module-level singletons shared by the whole process. NiceGUI supports multiple simultaneous browser clients hitting the same running server (e.g. two tabs, or a Colab proxy URL shared with someone else) — with this design, two concurrent sessions will overwrite each other's widget references and share one `ResearchController`'s project state, causing cross-talk, "client has been deleted" errors, or one user's run silently updating another user's screen.

**Proposed fix:** if this is always going to be single-user-per-instance (one person, one Colab notebook, one local run), this is low priority — just document it as a known constraint. If you ever want to let a small group share one running instance, move this state into NiceGUI's per-client storage (`app.storage.client` / a per-page closure) instead of module globals.

---

## P5 — Packaging: "install like a library from git"

### Issue 14: `pyproject.toml` won't actually give someone a runnable install

```toml
[project]
name = "khabrichacha"
version = "0.1.0"
description = "AI Powered Deep Research Framework"
requires-python = ">=3.10"
```
There's no `dependencies` list (everything needed only lives in `requirements.txt`, which `pip install git+https://...` never reads), no package-discovery configuration (so it's not guaranteed the sibling `deployment/` package — a plain top-level directory, not nested under `khabrichacha/` — gets included alongside `khabrichacha/`), no `package-data`/`MANIFEST.in` entries for the various `.yaml` config files the app needs at runtime, and no console-script entry point. Practically: `pip install git+https://github.com/you/khabrichacha` today would not reliably leave someone with a working, launchable app the way "install it like a library" implies.

**Proposed fix:**
```toml
[project]
name = "khabrichacha"
version = "0.1.0"
description = "AI Powered Deep Research Framework"
requires-python = ">=3.10"
dependencies = [
    "nicegui>=2.0.0", "uvicorn>=0.28.0", "loguru>=0.7.2",
    "openai>=1.12.0", "google-generativeai>=0.4.0",
    "requests>=2.31.0", "beautifulsoup4>=4.12.0", "readability-lxml>=0.8.1",
    "PyMuPDF>=1.23.0", "feedparser>=6.0.10", "ddgs",
    "pydantic>=2.0.0", "PyYAML>=6.0.1", "reportlab>=4.0.0",
    # keep transformers/torch optional — see Issue 4
]

[project.optional-dependencies]
local-llm = ["transformers>=4.38.0", "torch>=2.2.0"]

[project.scripts]
khabrichacha = "app:main"   # after wrapping app.py's body in a main() function

[tool.setuptools.packages.find]
include = ["khabrichacha*", "deployment*"]

[tool.setuptools.package-data]
"deployment" = ["*.yaml"]
```
This turns "clone it" into "`pip install .` (or `pip install git+...`) then run `khabrichacha`" — much closer to the "installed like other library" experience you're after, and it also fixes the currently-duplicated dependency list between `requirements.txt` and nothing.

### Issue 15: The main README's Quick Start is simply wrong

`README.md` says:
```
Run the Streamlit application interface:
streamlit run app.py
```
But `app.py` imports `from nicegui import ui` and calls `ui.run(...)` — this is a **NiceGUI** app. `streamlit` isn't even listed in `requirements.txt`. Tellingly, your *other* two docs already have the correct instruction: `README_ENVIRONMENT.md` ends with `python app.py`, and `setup_environment.sh` prints `"Environment setup complete! Run the app with: python app.py"` at the end of its own run. So this is purely a stale line in one file, not a real ambiguity in the codebase — but it's the very first thing anyone reads.

**Proposed fix:** delete the Streamlit line from `README.md`, replace with `python app.py` (or, once Issue 14 is done, `khabrichacha`), and take the opportunity to add the two or three paragraphs from this report's "real architecture" section — right now the README describes only `khabrichacha/core`, and a new contributor has no way to discover `deployment/runtime` exists at all from the docs.

---

## P6 — Smaller things worth cleaning up

- **Unused heavy dependency (see P1, Issue A for the fix):** Playwright + Chromium are installed/configured on Colab and locally but never imported by any tool — several minutes of install cost for a browsing capability that doesn't exist yet.
- **Empty `examples/` folder:** just a `.gitkeep`. For a "clone and run on Colab" story, a single example notebook (`.ipynb`) that runs `install_colab.py` then `launch_colab.py` would remove a lot of guesswork for a first-time user.
- **`LLMManager.get_provider()` never caches:** a brand-new provider object (and, for OpenAI/Gemini, a new client) is constructed on every single call. Harmless for correctness, but worth a simple cache keyed by `(provider_name, model)` once you're optimizing for latency/cost.

---

## Suggested order of attack (cheapest, most-unblocking first — no paid services required anywhere)

1. **Fix the `.gitignore` rule and restore/rewrite `deployment/workspace/`.** Nothing else on this list can even be tested until this exists — it's the one true P0.
2. **Fix `README.md`'s Quick Start** (NiceGUI, not Streamlit) — ten minutes, and it's the very first impression anyone gets.
3. **Fix the `pm`/`manifest` and `classifier` `NameError`s in `research_controller.py`, and make `start_research()` actually populate `result.errors`.** Without this, you can't even see that the structured pipeline is broken — it just fails silently.
4. **Wire `ConsensusEngine` into the STRUCTURED path, and broaden `structured_keywords` (or add an LLM-based intent classification step).** This is the actual centerpiece of your "main goal" — it turns "one lucky table wins" into a real cross-source, confidence-scored aggregation, and makes sure queries like your aviation example actually reach that pipeline in the first place.
5. **Add a Playwright-backed fetch fallback for JS-heavy pages.** You've already paid the install cost; wiring it in is what turns "static scraper" into something closer to a real browsing agent.
6. **Centralize provider instantiation + model verification into one helper.** This single change fixes the Transformers bug, the OpenRouter crash (once you either implement it or remove it from discovery), and deletes the 7× duplication in one pass.
7. **Swap `duckduckgo-search` → `ddgs`.** Keeps your only key-free search path healthy going forward; it's a drop-in rename.
8. **Escape text going into ReportLab, add a `.docx` builder with `python-docx`, and wire a real Downloads tab offering PDF/Word/Markdown.** This is the direct fix for your stated "get output as PDF, doc, or text" requirement.
9. **Make progress real and Stop actually stop.** Ties directly to your "see the progress" requirement.
10. **Pick a genuinely free-friendly local-model default** (small ungated model, or lead with Ollama) and give Ollama a realistic timeout.
11. **Tighten `pyproject.toml`** so `pip install` from git actually works end to end.
12. Only after the above: sandbox hardening and per-user state isolation, once you're thinking about more than one trusted local user.

Happy to help implement any of these next — the `deployment/workspace/` rebuild (item 1) or wiring `ConsensusEngine` into the structured pipeline (item 4) would be the highest-leverage places to start given what you just clarified about the project's real purpose.
