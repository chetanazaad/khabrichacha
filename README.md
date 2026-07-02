# Khabri Chacha

An agentic AI framework featuring dynamic planning, core task orchestration, multiple LLM providers, a clean tool registry, structured storage, and an elegant Streamlit UI.

## Project Structure
- `app.py`: Launcher script.
- `khabrichacha/core/`: Contains state, session, planning, and orchestrator modules.
- `khabrichacha/llm/`: Unified LLM adapter interface supporting OpenAI, Gemini, Ollama, and HuggingFace Transformers.
- `khabrichacha/tools/`: Extensible tools registry and built-in action runners.
- `khabrichacha/storage/`: Logic for listing, saving, and loading current workspace projects.
- `khabrichacha/ui/`: Sidebar controls, components, callbacks, and themes built on Streamlit.

## Quick Start

### 1. Installation
Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
Add your api keys inside `config.yaml` or set them as environment variables (e.g. `OPENAI_API_KEY`, `GEMINI_API_KEY`).

### 3. Run UI
Run the Streamlit application interface:
```bash
streamlit run app.py
```
