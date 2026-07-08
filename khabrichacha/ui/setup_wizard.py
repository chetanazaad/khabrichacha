import asyncio
import json
import sys
import subprocess
import requests
from nicegui import ui
from khabrichacha.core.model_recommender import recommend_model
from khabrichacha.ui.theme import get_custom_css

CORE_DEPS = {
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
    "ReportLab": "reportlab",
    "python-docx": "docx",
}

OPTIONAL_DEPS = {
    "OpenAI SDK": "openai",
    "Google GenAI": "google.generativeai",
    "Playwright": "playwright",
    "Transformers": "transformers",
    "Torch": "torch",
}

def check_missing_dependencies():
    missing_core = []
    missing_opt = []
    for name, import_name in CORE_DEPS.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_core.append(name)
    for name, import_name in OPTIONAL_DEPS.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_opt.append(name)
    return missing_core, missing_opt

def get_installed_ollama_models() -> list:
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []

@ui.page('/setup')
def setup_page():
    ui.add_head_html(get_custom_css())
    
    rec = recommend_model()
    hw = rec["hardware"]
    
    with ui.column().classes("w-full max-w-3xl mx-auto p-6 space-y-6"):
        # Header
        with ui.column().classes("text-center space-y-2 w-full"):
            ui.label("KhabriChacha").classes("text-4xl font-extrabold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400")
            ui.label("System Setup & Configuration Wizard").classes("text-gray-400 text-sm")
        
        # Step 1: Hardware Specs
        with ui.column().classes("panel w-full space-y-3"):
            ui.label("Step 1: Hardware Profile").classes("section-title")
            with ui.grid(columns=2).classes("w-full gap-4 text-sm text-gray-300"):
                ui.label(f"System RAM: {hw['ram_gb']} GB")
                ui.label(f"CPU Cores: {hw['cpu_cores']}")
                ui.label(f"GPU Detected: {hw['gpu_name']}")
                ui.label(f"GPU VRAM: {hw['gpu_vram_gb']} GB")
            
            with ui.row().classes("bg-indigo-950/40 border border-indigo-900/50 p-4 rounded-lg space-x-3 w-full items-start"):
                ui.icon("info", size="sm").classes("text-indigo-400 mt-0.5")
                with ui.column().classes("space-y-1"):
                    ui.label("Recommended AI Provider & Model").classes("text-xs font-bold uppercase tracking-wider text-indigo-300")
                    ui.label(f"Provider: {rec['provider'].upper()} | Model: {rec['model']}").classes("text-sm font-semibold text-white")
                    ui.label(rec["explanation"]).classes("text-xs text-gray-300")

        # Step 2: Dependencies
        missing_core, missing_opt = check_missing_dependencies()
        with ui.column().classes("panel w-full space-y-3"):
            ui.label("Step 2: Core Dependencies").classes("section-title")
            
            if not missing_core:
                with ui.row().classes("items-center space-x-2 text-emerald-400 text-sm"):
                    ui.icon("check_circle", size="sm")
                    ui.label("All core dependencies are installed!")
            else:
                ui.label("The following required dependencies are missing:").classes("text-xs text-rose-300")
                for dep in missing_core:
                    ui.label(f"• {dep}").classes("text-xs text-gray-400 ml-4")
                
                progress_deps = ui.linear_progress(value=0.0).classes("w-full")
                progress_deps.visible = False
                status_deps = ui.label("Ready to install core packages...").classes("text-xs text-gray-400")
                
                async def install_all_deps():
                    progress_deps.visible = True
                    total = len(missing_core)
                    for i, dep in enumerate(missing_core):
                        # Convert readable name to requirements name
                        pkg_map = {
                            "python-docx": "python-docx",
                            "ReportLab": "reportlab",
                            "Readability": "readability-lxml",
                            "PyMuPDF": "pymupdf",
                            "DuckDuckGo Search": "duckduckgo-search"
                        }
                        pkg_to_install = pkg_map.get(dep, dep.lower())
                        
                        status_deps.set_text(f"Installing {dep} ({i+1}/{total})...")
                        progress_deps.set_value(i / total)
                        
                        loop = asyncio.get_running_loop()
                        def run_pip():
                            cmd = f"{sys.executable} -m pip install {pkg_to_install} -q"
                            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                            return res.returncode == 0
                        
                        success = await loop.run_in_executor(None, run_pip)
                        if not success:
                            status_deps.set_text(f"Failed to install {dep}. Please run pip install manually.")
                            return
                    
                    status_deps.set_text("All core dependencies successfully installed! Please restart the server.")
                    progress_deps.set_value(1.0)
                    install_btn.disable()
                    check_ready_state()

                install_btn = ui.button("Install Core Dependencies", on_click=install_all_deps).classes("control-btn w-full")

        # Step 3: Model Setup
        with ui.column().classes("panel w-full space-y-3"):
            ui.label("Step 3: AI Model Setup").classes("section-title")
            
            SELECTABLE_MODELS = [
                "deepseek-r1:1.5b",
                "deepseek-r1:8b",
                "qwen2.5:3b",
                "qwen2.5:1.5b",
                "llama3:8b",
                "llama3:3b",
                "Cloud APIs (No Download Required)"
            ]
            
            if rec["provider"] in ["gemini", "openai"]:
                default_model = "Cloud APIs (No Download Required)"
            elif rec["model"] in SELECTABLE_MODELS:
                default_model = rec["model"]
            else:
                default_model = "qwen2.5:3b"
                
            model_select = ui.select(
                SELECTABLE_MODELS, 
                value=default_model, 
                label="Select Target LLM Model", 
                on_change=lambda: update_model_ui()
            ).classes("w-full")
            
            model_status_container = ui.column().classes("w-full space-y-3")

        # Step 4: Final Launch
        launch_btn = ui.button("Launch KhabriChacha Application", on_click=lambda: ui.navigate.to('/')).classes("control-btn w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-bold").disable()
        
        def check_ready_state():
            missing_c, _ = check_missing_dependencies()
            if missing_c:
                launch_btn.disable()
                return
            
            selected_model = model_select.value
            if selected_model == "Cloud APIs (No Download Required)":
                launch_btn.enable()
                return
                
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=1)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    model_exists = any(m.startswith(selected_model.split(":")[0]) for m in models)
                    if model_exists:
                        launch_btn.enable()
                        return
            except Exception:
                pass
            launch_btn.disable()

        def update_model_ui():
            model_status_container.clear()
            selected = model_select.value
            
            with model_status_container:
                if selected == "Cloud APIs (No Download Required)":
                    ui.label("Your system will run using Cloud APIs. No model download required.").classes("text-sm text-gray-300")
                    ui.label("Please ensure your API keys (e.g. GEMINI_API_KEY, OPENAI_API_KEY) are configured in your environment.").classes("text-xs text-amber-400")
                    check_ready_state()
                    return
                
                # Check Ollama status
                ollama_running = False
                installed_models = []
                try:
                    resp = requests.get("http://localhost:11434/api/tags", timeout=1)
                    if resp.status_code == 200:
                        ollama_running = True
                        installed_models = [m["name"] for m in resp.json().get("models", [])]
                except Exception:
                    pass
                
                if not ollama_running:
                    with ui.row().classes("bg-rose-950/40 border border-rose-900/50 p-4 rounded-lg space-x-3 w-full items-start"):
                        ui.icon("warning", size="sm").classes("text-rose-400 mt-0.5")
                        with ui.column().classes("space-y-1"):
                            ui.label("Ollama is not running!").classes("text-xs font-bold uppercase tracking-wider text-rose-300")
                            ui.label("To download or use local models, you must start Ollama on your machine first. If Ollama is not installed, download it from https://ollama.com.").classes("text-xs text-gray-300")
                    check_ready_state()
                    return
                
                with ui.row().classes("items-center space-x-2 text-emerald-400 text-sm"):
                    ui.icon("check_circle", size="sm")
                    ui.label("Ollama service detected and running locally.")
                
                model_exists = any(m.startswith(selected.split(":")[0]) for m in installed_models)
                
                if model_exists:
                    with ui.row().classes("items-center space-x-2 text-emerald-400 text-sm"):
                        ui.icon("check_circle", size="sm")
                        ui.label(f"Model '{selected}' is already downloaded!")
                else:
                    ui.label(f"Model '{selected}' is not downloaded yet.").classes("text-xs text-amber-300")
                    
                    progress_model = ui.linear_progress(value=0.0).classes("w-full")
                    progress_model.visible = False
                    status_model = ui.label("Ready to pull model...").classes("text-xs text-gray-400")
                    
                    async def pull_model():
                        progress_model.visible = True
                        pull_btn.disable()
                        url = "http://localhost:11434/api/pull"
                        payload = {"name": selected}
                        try:
                            loop = asyncio.get_running_loop()
                            def start_stream():
                                return requests.post(url, json=payload, stream=True, timeout=120)
                            
                            response = await loop.run_in_executor(None, start_stream)
                            for line in response.iter_lines():
                                if not line:
                                    continue
                                data = json.loads(line.decode('utf-8'))
                                status = data.get("status", "")
                                completed = data.get("completed", 0)
                                total = data.get("total", 0)
                                
                                if total > 0:
                                    progress = completed / total
                                    progress_model.set_value(progress)
                                    status_model.set_text(f"Downloading: {status} ({round(progress * 100, 1)}%)")
                                else:
                                    status_model.set_text(f"Downloading: {status}")
                            
                            status_model.set_text(f"Successfully downloaded and loaded {selected}!")
                            progress_model.set_value(1.0)
                            update_model_ui()
                        except Exception as e:
                            status_model.set_text(f"Error pulling model: {e}")
                            pull_btn.enable()

                    pull_btn = ui.button(f"Download model ({selected})", on_click=pull_model).classes("control-btn w-full")
                
                check_ready_state()

        # Run initial state verification check
        update_model_ui()

