# KhabriChacha Environment Setup Guide

This guide explains how to properly set up the Python environment to run KhabriChacha without encountering `ModuleNotFoundError`.

## Prerequisites
- **Python Version**: Recommended **Python 3.10+**.

## Quick Start (Automated Setup)

We have provided automated scripts to create a virtual environment, upgrade pip, install all dependencies, and verify the installation.

### On Windows
Open PowerShell and run:
```powershell
.\setup_environment.ps1
```

### On Linux / macOS
Open Terminal and run:
```bash
./setup_environment.sh
```

## Manual Setup

If you prefer to set up the environment manually, follow these steps:

### 1. Create a Virtual Environment
**Windows**:
```cmd
python -m venv .venv
```
**Linux / macOS**:
```bash
python3 -m venv .venv
```

### 2. Activate the Virtual Environment
**Windows**:
```cmd
.\.venv\Scripts\activate
```
**Linux / macOS**:
```bash
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verify Installation
Run the included verification script to ensure all packages are correctly installed:
```bash
python verify_environment.py
```

## Dependency Map (Package vs Import Name)

If you encounter a missing module error, be aware that some package names in `requirements.txt` differ from their import names in Python.

| Package Name | Import Name | Used In |
| --- | --- | --- |
| `beautifulsoup4` | `bs4` | `fetch_page` |
| `readability-lxml` | `readability` | `fetch_page` |
| `duckduckgo-search` | `duckduckgo_search` | `search_web` |
| `PyMuPDF` | `fitz` | `fetch_pdf` |
| `google-generativeai` | `google.generativeai` | `llm.providers.gemini` |
| `PyYAML` | `yaml` | `session` |

## Common Errors & Troubleshooting

- **`ModuleNotFoundError: No module named 'duckduckgo_search'`**
  - **Fix**: You need to run `pip install duckduckgo-search` (note the hyphen).
- **`ModuleNotFoundError: No module named 'fitz'`**
  - **Fix**: You need to run `pip install PyMuPDF`. Do NOT install `fitz` directly.
- **`requests or beautifulsoup4 package is not installed`**
  - **Fix**: Run `pip install requests beautifulsoup4`.
- **`readability-lxml is not installed. Will fallback to BeautifulSoup.`**
  - **Fix**: Run `pip install readability-lxml` to enable advanced text extraction from articles.

Once setup is complete and `verify_environment.py` passes, you can launch the application:
```bash
python app.py
```
