# Khabri Chacha

An agentic AI research framework: point it at a question, and it searches
the web, browses pages (rendering JavaScript when needed), reconciles facts
across sources, and hands back a sourced answer as Markdown, JSON, PDF, or
Word — with a UI to enter the request and watch progress in real time.
Built to run entirely for free: no LLM API key required if you use a local
model via Ollama (e.g. `qwen2.5:3b`).

## Project Structure
- `app.py`: Launcher script (NiceGUI).
- `khabrichacha/core/`: Simpler orchestrator + planner engine, reused by the
  RESEARCH/DEEP_RESEARCH strategies below.
- `khabrichacha/llm/`: Unified LLM adapter interface supporting OpenAI,
  OpenRouter, Gemini, Ollama, and local Hugging Face Transformers models.
- `khabrichacha/tools/`: Extensible tools registry and built-in action
  runners (web search, page fetch/browse, PDF fetch, Python execution).
- `khabrichacha/ui/`: Pages, components, callbacks, and theming — built on
  **NiceGUI**, not Streamlit.
- `deployment/runtime/`: The main research engine — classifies each query
  into a strategy (FAST / LOOKUP / STRUCTURED / COMPARISON / ANALYSIS /
  RESEARCH / DEEP_RESEARCH) and runs a purpose-built pipeline for it,
  including cross-source numeric consensus and trust-ranked retrieval.
- `deployment/workspace/`: On-disk project storage, caching, and asset
  management.
- `deployment/reporting/`: Turns a finished run into report.md / .json /
  .pdf / .docx.

## Quick Start

### 1. Installation
Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up a free local model (recommended) — or use an API key
**Local, free, no API key (recommended):** install [Ollama](https://ollama.com),
then pull a small model:
```bash
ollama pull qwen2.5:3b
```
The app will automatically detect it once Ollama is running.

**Optional — better relevance filtering:** pull a small embedding model too:
```bash
ollama pull nomic-embed-text
```
This lets the research pipeline recognize genuinely relevant sources that
are worded differently from your question (paraphrases, synonyms) instead
of relying on keyword overlap alone. It's auto-detected with no extra
configuration; if it isn't pulled, everything still works using keyword-
based relevance matching.

**Or, use a hosted API instead:** set one of these as an environment
variable — `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`
(OpenRouter has several free-tier models too). API keys are read from the
environment, not from `config.yaml`.

### 3. Run the UI
```bash
python app.py
```
This starts a NiceGUI server at `http://127.0.0.1:8080`.

### 4. Run on Google Colab
See `deployment/launchers/install_colab.py` and `launch_colab.py`, or
`colab_utils.py` for a guided setup that installs dependencies (including
a headless browser for JS-rendered pages) and launches the UI from a
notebook cell.

### 5. Broader search coverage (optional)
By default, web search uses DuckDuckGo, which needs no setup. For
meaningfully broader coverage, you can self-host
[SearxNG](https://github.com/searxng/searxng) (a metasearch engine that
aggregates results across many search engines) with a single command:
```bash
docker run -d -p 8888:8888 searxng/searxng
```
Then set the `SEARXNG_URL` environment variable (e.g.
`SEARXNG_URL=http://localhost:8888`) before starting the app. Results
from SearxNG and DuckDuckGo are merged and deduplicated automatically —
if `SEARXNG_URL` isn't set, nothing changes; DuckDuckGo alone is used.
