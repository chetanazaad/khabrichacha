from nicegui import ui
import khabrichacha.ui.ui_state as ui_state
from khabrichacha.ui.callbacks import (
    run_research,
    run_research_clicked,
    pause_research,
    resume_research,
    stop_research,
    load_project,
)


def build_layout():
    with ui.element("div").classes("w-full min-h-screen p-3 flex flex-col gap-3"):
        _build_status_bar()
        with ui.row().classes("w-full flex-1 gap-3 min-h-0"):
            _build_left_nav()
            _build_mission_panel()
            _build_right_panel()


MOCK_PROJECTS = ["AI Chips", "India Budget", "NVIDIA", "Iran", "Taiwan"]
PROVIDERS = [
    ("Web", True),
    ("News", True),
    ("Government", False),
    ("Reddit", False),
    ("GitHub", True),
    ("Academic", True),
    ("PDF", False),
    ("Images", False),
]


def _build_status_bar():
    with ui.row().classes("w-full status-bar items-center gap-6 px-4 py-2"):
        with ui.row().classes("items-center gap-2"):
            ui.label("\U0001f4f0 KhabriChacha").classes("text-lg font-bold text-white")
        with ui.row().classes("items-center gap-2"):
            ui.label("\U0001f4c1 Project:").classes("text-xs text-gray-400")
            ui_state.project_label = ui.label("Untitled").classes("text-xs font-semibold text-indigo-300")
        with ui.row().classes("items-center gap-2"):
            ui.label("\U0001f916 Model:").classes("text-xs text-gray-400")
            ui_state.model_label = ui.label("None").classes("text-xs font-semibold text-indigo-300")
        with ui.row().classes("items-center gap-2 ml-auto"):
            ui.label("\U0001f7e2 Status:").classes("text-xs text-gray-400")
            ui_state.status_label = ui.label("Ready").classes("status-badge status-ready")


def _build_left_nav():
    with ui.column().classes("w-[220px] flex-shrink-0 panel gap-1"):
        ui.html('<div class="section-title">\U0001f4c0 Navigation</div>')

        for label, icon, active in [
            ("Projects", "\U0001f4c2", True),
            ("Models", "\U0001f916", False),
            ("Settings", "\u2699", False),
            ("Logs", "\U0001f4dc", False),
            ("About", "\u2139", False),
        ]:
            btn = ui.button(f"{icon} {label}", on_click=lambda l=label: ui.notify(f"Navigate: {l}"))
            btn.classes("nav-btn" + (" active" if active else ""))

        ui.html('<hr class="border-gray-700 my-2">')
        ui.html('<div class="text-xs text-gray-500 font-semibold px-2 mb-1">\U0001f4c2 WORKSPACE</div>')
        with ui.expansion("Projects", icon="folder").classes("w-full text-sm text-gray-300"):
            for proj in MOCK_PROJECTS:
                pbtn = ui.button(proj, on_click=lambda p=proj: load_project(p))
                pbtn.classes("nav-btn text-xs pl-4")


def _build_mission_panel():
    with ui.column().classes("flex-1 panel gap-3"):
        ui.html('<div class="section-title">\U0001f30d Research Mission</div>')

        ui_state.goal_input = ui.textarea("Mission Objective").classes("w-full").props(
            "placeholder='Describe your research mission. What evidence, comparisons, or references are needed?\\ne.g. Analyze the competitive landscape of AI chip manufacturers...'"
        )

        ui.html('<div class="text-xs text-gray-400 font-semibold mt-1">Research Providers</div>')
        with ui.row().classes("w-full gap-2 flex-wrap"):
            for idx, (name, checked) in enumerate(PROVIDERS):
                cb = ui.checkbox(name, value=checked)
                cb.classes("text-sm text-gray-300 provider-cb")

        with ui.row().classes("w-full gap-4 mt-1"):
            ui_state.model_select = ui.select(
                label="Model",
                options=["gpt-4", "gpt-3.5-turbo", "gemini-pro", "claude-3", "ollama/llama3"],
                value="gpt-4",
            ).classes("flex-1")

            ui_state.depth_select = ui.select(
                label="Depth",
                options=["Quick", "Standard", "Deep", "Extreme"],
                value="Standard",
            ).classes("w-32")

            ui_state.sources_input = ui.number(
                label="Max Sources",
                value=5, min=1, max=20,
            ).classes("w-28")

        with ui.row().classes("w-full gap-2 mt-1"):
            ui.button("Run", on_click=run_research_clicked).classes("control-btn")
            ui.button("Pause", on_click=pause_research).classes("control-btn secondary")
            ui.button("Resume", on_click=resume_research).classes("control-btn secondary")
            ui.button("Stop", on_click=stop_research).classes("control-btn secondary")


def _build_right_panel():
    with ui.column().classes("w-[33%] flex-shrink-0 gap-3"):
        _build_progress_header()
        _build_tabbed_workspace()


def _build_progress_header():
    with ui.column().classes("panel gap-2"):
        ui.html('<div class="section-title">\u25b6 Execution Progress</div>')
        ui_state.progress_bar = ui.linear_progress(value=0.0).classes("w-full")
        with ui.row().classes("w-full items-center justify-between"):
            ui_state.progress_label = ui.label("Step 0 of 0").classes("text-xs text-gray-400")
            ui.label("Ready").classes("text-xs text-gray-500")


def _build_tabbed_workspace():
    with ui.element("div").classes("panel flex-1 flex flex-col"):
        with ui.tabs().classes("w-full") as tabs:
            tab_results = ui.tab("Results", icon="description")
            tab_refs = ui.tab("References", icon="link")
            tab_downloads = ui.tab("Downloads", icon="download")
            tab_logs = ui.tab("Logs", icon="terminal")

        with ui.tab_panels(tabs, value=tab_results).classes("w-full flex-1"):
            with ui.tab_panel(tab_results):
                ui_state.results_markdown = ui.markdown("_No results yet. Run a research mission to see output._").classes("results-panel")

            with ui.tab_panel(tab_refs):
                ui_state.references_markdown = ui.markdown("_No references collected._").classes("results-panel text-sm")

            with ui.tab_panel(tab_downloads):
                ui.markdown("_No downloads available._").classes("results-panel text-sm")

            with ui.tab_panel(tab_logs):
                ui_state.log_view = ui.log().classes("w-full log-view h-64")
