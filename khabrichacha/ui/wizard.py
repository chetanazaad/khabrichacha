from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Optional, Callable

from nicegui import ui


class SetupWizard:
    def __init__(self, on_launch: Optional[Callable[[], None]] = None) -> None:
        self.state = {}
        self.container = None
        self._on_launch = on_launch

    def render(self) -> None:
        self.container = ui.column().classes("w-full min-h-screen p-4 gap-4")
        with self.container:
            ui.html('<div class="text-2xl font-semibold text-white">Setup Wizard</div>')
            ui.markdown("This wizard detects your machine profile, offers an Ollama setup path, and then launches the research UI.")
            self._render_system_summary()
            self._render_install_steps()
            self._render_launch_button()

    def _render_system_summary(self) -> None:
        cpu_count = os.cpu_count() or 0
        ram_gb = "unknown"
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        except Exception:
            pass
        gpu_present = os.environ.get("CUDA_VISIBLE_DEVICES") not in (None, "") or os.path.exists("/dev/nvidia0")
        with ui.card().classes("w-full bg-gray-900 text-gray-200"):
            ui.label(f"OS: {platform.system()} {platform.release()}").classes("text-sm")
            ui.label(f"CPU cores: {cpu_count}").classes("text-sm")
            ui.label(f"RAM: {ram_gb} GB").classes("text-sm")
            ui.label(f"GPU detected: {'yes' if gpu_present else 'no'}").classes("text-sm")

    def _render_install_steps(self) -> None:
        with ui.card().classes("w-full bg-gray-900 text-gray-200"):
            ui.label("Suggested setup").classes("text-sm font-semibold")
            ui.label("- Install Ollama using the platform-specific flow below.").classes("text-sm")
            ui.label("- Pull a small and a large model for local use.").classes("text-sm")
            ui.label("- Install Python dependencies from requirements.txt.").classes("text-sm")

            with ui.row().classes("w-full gap-2"):
                ui.button("Install Ollama", on_click=self._install_ollama).classes("bg-indigo-600 text-white")
                ui.button("Install Models", on_click=self._install_models).classes("bg-emerald-600 text-white")
                ui.button("Install Python deps", on_click=self._install_python_deps).classes("bg-amber-600 text-white")

    def _render_launch_button(self) -> None:
        with ui.card().classes("w-full bg-gray-900 text-gray-200"):
            ui.button("Launch Research UI", on_click=self._launch_ui).classes("bg-fuchsia-600 text-white")

    def _install_ollama(self) -> None:
        ui.notify("Installing Ollama. This may take a few minutes.", type="info")
        if platform.system() == "Windows":
            subprocess.Popen(["winget", "install", "--id", "Ollama.Ollama", "-e"], shell=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(["/bin/bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], shell=False)
        else:
            subprocess.Popen(["/bin/bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], shell=False)

    def _install_models(self) -> None:
        ui.notify("Pulling suggested Ollama models.", type="info")
        try:
            subprocess.Popen(["ollama", "pull", "qwen2.5:3b"], shell=True)
            subprocess.Popen(["ollama", "pull", "qwen2.5:14b"], shell=True)
        except Exception as exc:
            ui.notify(f"Failed to start model install: {exc}", type="negative")

    def _install_python_deps(self) -> None:
        ui.notify("Installing Python dependencies.", type="info")
        try:
            subprocess.Popen([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], shell=True)
        except Exception as exc:
            ui.notify(f"Failed to start dependency install: {exc}", type="negative")

    def _launch_ui(self) -> None:
        ui.notify("Launching the research UI.", type="positive")
        if self._on_launch is not None:
            self._on_launch()
            return
        from khabrichacha.ui.main import start_application
        start_application()
