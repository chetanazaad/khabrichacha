import sys

# Dictionary mapping Package Name -> Import Name (or test code)
DEPENDENCIES = {
    "NiceGUI": "nicegui",
    "Loguru": "loguru",
    "Uvicorn": "uvicorn",
    "Watchdog": "watchdog",
    "Rich": "rich",
    "PyYAML": "yaml",
    "Pydantic": "pydantic",
    "Requests": "requests",
    "BeautifulSoup4": "bs4",
    "DuckDuckGo": "duckduckgo_search",
    "PyMuPDF": "fitz",
    "Readability-lxml": "readability",
    "Feedparser": "feedparser",
    "Pandas": "pandas",
    "NumPy": "numpy",
    "Transformers": "transformers",
    "Torch": "torch",
    "OpenAI": "openai",
    "Google GenerativeAI": "google.generativeai",
}

def verify_environment():
    print("=" * 50)
    print("KhabriChacha Environment Verification")
    print("=" * 50)
    
    all_passed = True
    for pkg_name, import_name in DEPENDENCIES.items():
        try:
            __import__(import_name)
            print(f"[OK] Installed: {pkg_name} (import {import_name})")
        except ImportError:
            print(f"[X]  Missing  : {pkg_name} (import {import_name})")
            all_passed = False
            
    print("=" * 50)
    if all_passed:
        print("All dependencies are successfully installed! You are ready to go.")
        sys.exit(0)
    else:
        print("WARNING: Some dependencies are missing. Please run the setup scripts or `pip install -r requirements.txt`.")
        sys.exit(1)

if __name__ == "__main__":
    verify_environment()
