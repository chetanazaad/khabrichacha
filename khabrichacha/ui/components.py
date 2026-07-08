from nicegui import ui
import khabrichacha.ui.ui_state as ui_state
from khabrichacha.ui.callbacks import (
    run_research,
    run_research_clicked,
    pause_research,
    resume_research,
    stop_research,
    load_project,
    save_project_clicked,
    _workspace_manager,
    _provider_manager,
)


def build_layout():
    with ui.element("div").classes("w-full min-h-screen p-3 flex flex-col gap-3"):
        _build_status_bar()
        with ui.row().classes("w-full flex-1 gap-3 min-h-0"):
            _build_left_nav()
            _build_mission_panel()
            _build_right_panel()


def _get_project_list():
    """Load projects from ProjectManager; fall back to empty list."""
    try:
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(_workspace_manager)
        return pm.list_projects()
    except Exception:
        return []


def _get_model_options():
    """Discover available models from ProviderManager; fall back to defaults."""
    try:
        options = _provider_manager.get_available_models()
        if options:
            return options
    except Exception as e:
        print(f"Error getting model options: {e}")
    return ["openai/gpt-4o", "gemini/gemini-2.0-flash", "ollama/llama3"]
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
            projects = _get_project_list()
            if projects:
                for proj in projects:
                    display = proj.title or proj.project_id
                    pbtn = ui.button(display, on_click=lambda pid=proj.project_id: load_project(pid))
                    pbtn.classes("nav-btn text-xs pl-4")
            else:
                ui.label("No projects yet").classes("text-xs text-gray-500 px-2")

        ui.html('<hr class="border-gray-700 my-2">')
        ui.html('<div class="text-xs text-gray-500 font-semibold px-2 mb-1">\u26a1 SYSTEM STATUS</div>')
        _build_system_status()

def _build_system_status():
    """Builds a small panel showing provider health."""
    try:
        providers = _provider_manager.discover_providers()
        
        with ui.column().classes("w-full px-2 py-1 bg-gray-800 rounded text-xs gap-1"):
            for p_name, data in providers.items():
                if data["available"]:
                    icon, color = "\U0001f7e2", "text-green-400"
                    text = f"{p_name} ({len(data['models'])} models)"
                elif data["configured"] and not data["available"]:
                    icon, color = "\U0001f7e0", "text-orange-400"
                    text = f"{p_name} (error)"
                else:
                    icon, color = "\u26aa", "text-gray-500"
                    text = f"{p_name} (unconfigured)"
                    
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(text).classes(f"{color}")
                    ui.label(icon).classes("text-[10px]")
    except Exception as e:
        ui.label(f"Status error: {e}").classes("text-xs text-red-500 px-2")


def _build_mission_panel():
    with ui.column().classes("flex-1 panel gap-3"):
        ui.html('<div class="section-title">\U0001f30d Research Mission</div>')

        ui_state.goal_input = ui.textarea("Mission Objective").classes("w-full").props(
            "placeholder='Describe your research mission. What evidence, comparisons, or references are needed?\\ne.g. Analyze the competitive landscape of AI chip manufacturers...'"
        ).on('keyup', lambda: None)

        ui.html('<div class="text-xs text-gray-400 font-semibold mt-1">Research Providers</div>')
        with ui.row().classes("w-full gap-2 flex-wrap"):
            for idx, (name, checked) in enumerate(PROVIDERS):
                cb = ui.checkbox(name, value=checked)
                cb.classes("text-sm text-gray-300 provider-cb")

        with ui.row().classes("w-full gap-4 mt-1"):
            model_options = _get_model_options()
            ui_state.model_select = ui.select(
                label="Model",
                options=model_options,
                value=model_options[0] if model_options else "gpt-4",
            ).classes("flex-1")

            ui_state.strategy_select = ui.select(
                label="Strategy",
                options=["Auto (Recommended)", "Fast Answer", "Lookup",
                         "Structured Data", "Comparison", "Analysis",
                         "Research", "Deep Research"],
                value="Auto (Recommended)",
            ).classes("w-40")

            ui_state.sources_input = ui.number(
                label="Max Sources",
                value=5, min=1, max=20,
            ).classes("w-28")

        with ui.row().classes("w-full gap-2 mt-1"):
            ui.button("Run", on_click=run_research_clicked).classes("control-btn")
            ui.button("Pause", on_click=pause_research).classes("control-btn secondary")
            ui.button("Resume", on_click=resume_research).classes("control-btn secondary")
            ui.button("Stop", on_click=stop_research).classes("control-btn secondary")
            ui_state.save_project_btn = ui.button("Save Project", on_click=save_project_clicked).classes("control-btn").props("disable")


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

        ui.html('<hr class="border-gray-700 my-1">')
        ui.html('<div class="text-[10px] text-indigo-400 font-semibold uppercase tracking-wider">Strategy & Routing</div>')
        with ui.row().classes("w-full gap-4 text-xs"):
            ui_state.strategy_indicator = ui.label("Strategy: —").classes("text-indigo-300 font-semibold")
            ui_state.confidence_indicator = ui.label("Confidence: —").classes("text-gray-400")
            ui_state.latency_indicator = ui.label("Est. Time: —").classes("text-gray-400")
            ui_state.cost_indicator = ui.label("Est. Cost: —").classes("text-gray-400")
            
        with ui.row().classes("w-full gap-3 text-[10px] text-gray-500"):
            ui_state.planner_indicator = ui.label("Planner: —")
            ui_state.search_indicator = ui.label("Search: —")
            ui_state.reasoning_indicator = ui.label("Reasoning: —")
            ui_state.evidence_indicator = ui.label("Evidence: —")
            ui_state.report_indicator = ui.label("Report: —")
            ui_state.project_indicator = ui.label("Project: —")

        ui.html('<hr class="border-gray-700 my-1">')
        ui.html('<div class="text-[10px] text-indigo-400 font-semibold uppercase tracking-wider">Retrieval & Consensus</div>')
        with ui.row().classes("w-full gap-3 text-[10px] text-gray-400 flex-wrap"):
            ui_state.sources_found_indicator = ui.label("Found: —")
            ui_state.sources_selected_indicator = ui.label("Selected: —")
            ui_state.duplicates_removed_indicator = ui.label("Duplicates: —")
            ui_state.trust_score_indicator = ui.label("Avg Trust: —")
            ui_state.output_format_indicator = ui.label("Format: —")
            ui_state.knowledge_cache_indicator = ui.label("Cache Hits: —")
            ui_state.consensus_score_indicator = ui.label("Consensus: —")


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
                ui_state.downloads_container = ui.column().classes("w-full gap-2")
                with ui_state.downloads_container:
                    ui.markdown("_No downloads available._").classes("results-panel text-sm")

            with ui.tab_panel(tab_logs):
                ui_state.log_view = ui.log().classes("w-full log-view h-64")
