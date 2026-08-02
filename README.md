# Khabri Chacha AI

An agentic AI research framework: point it at a question, and it classifies the intent, dynamically builds a search plan, browses pages (rendering JavaScript when needed), extracts consensus facts, and outputs synthesized reports as Markdown, JSON, PDF, or Word documents.

This application features a modern **Perplexity / ChatGPT-style user interface** with a collapsible left sidebar, dynamic workspaces, real-time trace indicators, and live execution logs.

---

## 🚫 Proprietary License Warning
This repository is published under a proprietary license. While the source code is public for educational review and discovery purposes, **copying, cloning, distributing, modifications, or commercial reuse of this software is strictly prohibited** without prior written consent. Refer to the [LICENSE](LICENSE) file for the full terms.

---

## Architecture & Project Structure
- `app.py`: Main entry point (NiceGUI launcher script running on port `8085`).
- `khabrichacha/core/`: Simpler orchestrator and planner engine.
- `khabrichacha/llm/`: Unified LLM adapter supporting OpenAI, OpenRouter, Gemini, Ollama, and local Hugging Face Models.
- `khabrichacha/tools/`: Extensible tools registry (web search, JS rendering, page fetching, PDF parsing).
- `khabrichacha/ui/`: ChatGPT/Perplexity collapsible layout, pages, callbacks, and theme styling built on NiceGUI.
- `deployment/runtime/`: The research engine - classifies each query (FAST, LOOKUP, STRUCTURED, COMPARISON, ANALYSIS, RESEARCH, DEEP_RESEARCH) and runs target pipelines.
- `deployment/workspace/`: On-disk project storage, caching, and asset management.
- `deployment/reporting/`: Converts research outcomes into ReportLab PDF, Docx, Markdown, and JSON.

---

## Installation & Setup

### 1. Requirements & Dependencies
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Local Models (Free & Local)
Install [Ollama](https://ollama.com). Start the Ollama service, then pull the recommended models:

- **Fast Router Model (LLM-1):**
  ```bash
  ollama pull qwen2.5:0.5b
  ```
- **Reasoning & Synthesis Model (LLM-2):**
  ```bash
  ollama pull qwen2.5:3b
  ```
- **Embedding Model (Optional - for high-consensus grounding):**
  ```bash
  ollama pull nomic-embed-text
  ```

*Alternatively, you can configure hosted API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`) in your environment.*

### 3. Web Search METASEARCH Configuration
By default, KhabriChacha routes search queries through public metasearch aggregator engines and DuckDuckGo. 
The configuration is pointing to a free, public SearxNG instance `https://searx.be` in `config.yaml`, eliminating the need to set up Docker containers locally.

---

## Running the Application

To launch the web interface:
```bash
python app.py
```
This will start the local server on `http://127.0.0.1:8085`.

### Key Interface Features:
- **Collapsible Sidebar:** Toggle the sidebar drawer via the top-left hamburger menu.
- **"+ New Chat" Button:** Instantly starts a fresh session, clearing active cache.
- **Projects Grid View:** Manage, load, and download past research sessions.
- **Dual-LLM Status selectors:** Swap LLM-1 and LLM-2 models on the fly in the header.
