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
    navigate_to_page,
)


def build_layout():
    with ui.element("div").classes("w-full h-screen max-h-screen p-3 flex flex-col gap-2 bg-[#0b0f19] text-gray-100 overflow-hidden"):
        _build_status_bar()
        with ui.row().classes("w-full flex-1 gap-3 min-h-0 overflow-hidden"):
            _build_left_nav()
            _build_chat_workspace()
            _build_right_panel()


def _get_project_list():
    """Load projects from ProjectManager; fall back to empty list."""
    try:
        from deployment.config_loader import load_config
        from deployment.workspace.workspace_manager import WorkspaceManager
        from deployment.workspace.project_manager import ProjectManager
        config = load_config()
        ws = WorkspaceManager(config.workspace.root)
        pm = ProjectManager(ws)
        return pm.list_projects()
    except Exception:
        return []


def _get_model_options():
    """Discover available models from ProviderManager; fall back to defaults."""
    try:
        from khabrichacha.providers.provider_manager import ProviderManager
        from deployment.config_loader import load_config
        config = load_config()
        pm = ProviderManager(config.model_dump())
        options = pm.get_available_models()
        if options:
            return options
    except Exception as e:
        print(f"Error getting model options: {e}")
    return ["ollama/qwen2.5:3b", "openai/gpt-4o", "gemini/gemini-2.0-flash"]


def _build_status_bar():
    model_options = _get_model_options()
    default_router = model_options[0] if model_options else "gemini/gemini-2.0-flash"
    for m in model_options:
        if "0.5b" in m or "3b" in m or "mini" in m or "flash" in m:
            default_router = m
            break

    default_analysis = model_options[0] if model_options else default_router
    for m in model_options:
        if m != default_router and not ("0.5b" in m):
            default_analysis = m
            break

    with ui.row().classes("w-full status-bar items-center justify-between px-4 py-2 gap-2 flex-shrink-0"):
        with ui.row().classes("items-center gap-2"):
            ui.label("KhabriChacha AI").classes("text-lg font-bold text-white tracking-wide")
            ui.label("Dual-LLM Engine").classes("text-[10px] bg-indigo-900/60 text-indigo-300 border border-indigo-500/40 px-2 py-0.5 rounded-full font-mono")

        with ui.row().classes("items-center gap-4 flex-wrap"):
            with ui.row().classes("items-center gap-2"):
                ui.label("LLM-1 (Router):").classes("text-xs text-indigo-300 font-semibold")
                ui_state.router_model_select = ui.select(
                    options=model_options,
                    value=default_router
                ).props("dense options-dense borderless").classes("text-xs bg-gray-900/80 rounded px-2 py-0.5 text-indigo-200 border border-indigo-500/30")

            with ui.row().classes("items-center gap-2"):
                ui.label("LLM-2 (Analysis):").classes("text-xs text-purple-300 font-semibold")
                ui_state.analysis_model_select = ui.select(
                    options=model_options,
                    value=default_analysis
                ).props("dense options-dense borderless").classes("text-xs bg-gray-900/80 rounded px-2 py-0.5 text-purple-200 border border-purple-500/30")

        with ui.row().classes("items-center gap-3 ml-auto"):
            with ui.row().classes("items-center gap-1.5"):
                ui.label("Project:").classes("text-xs text-gray-400")
                ui_state.project_label = ui.label("Chat Session").classes("text-xs font-semibold text-indigo-300")
            ui_state.status_label = ui.label("Ready").classes("status-badge status-ready")


def _build_left_nav():
    with ui.column().classes("w-[220px] flex-shrink-0 panel gap-1 h-full overflow-hidden"):
        ui.html('<div class="section-title">Workspace</div>')

        for label, icon, active in [
            ("Research Chat", "", True),
            ("Projects", "", False),
            ("Models", "", False),
            ("Settings", "", False),
            ("Logs", "", False),
        ]:
            btn = ui.button(f"{icon} {label}", on_click=lambda l=label: navigate_to_page(l))
            btn.classes("nav-btn" + (" active" if active else ""))

        ui.html('<hr class="border-gray-700/60 my-2">')
        ui.html('<div class="text-[10px] text-gray-400 font-semibold px-2 mb-1 uppercase tracking-wider">Saved Projects</div>')
        with ui.column().classes("w-full gap-1 overflow-y-auto max-h-48"):
            projects = _get_project_list()
            if projects:
                for proj in projects:
                    display = proj.title or proj.project_id
                    pbtn = ui.button(display[:22], on_click=lambda pid=proj.project_id: load_project(pid))
                    pbtn.classes("nav-btn text-xs pl-2 text-left truncate")
            else:
                ui.label("No saved projects yet").classes("text-xs text-gray-500 px-2")

        ui.html('<hr class="border-gray-700/60 my-2">')
        ui.html('<div class="text-[10px] text-gray-400 font-semibold px-2 mb-1 uppercase tracking-wider">Providers</div>')
        _build_system_status()


def _build_system_status():
    """Builds a small panel showing provider health."""
    try:
        from khabrichacha.providers.provider_manager import ProviderManager
        from deployment.config_loader import load_config
        config = load_config()
        pm = ProviderManager(config.model_dump())
        providers = pm.discover_providers()
        
        with ui.column().classes("w-full px-2 py-1 bg-gray-900/60 rounded border border-gray-800 text-xs gap-1"):
            for p_name, data in providers.items():
                if data["available"]:
                    icon, color = "🟢", "text-green-400"
                    text = f"{p_name} ({len(data['models'])})"
                elif data["configured"] and not data["available"]:
                    icon, color = "🟠", "text-orange-400"
                    text = f"{p_name}"
                else:
                    icon, color = "⚪", "text-gray-500"
                    text = f"{p_name}"
                    
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(text).classes(f"{color} text-[11px]")
                    ui.label(icon).classes("text-[9px]")
    except Exception as e:
        ui.label(f"Status error: {e}").classes("text-xs text-red-500 px-2")


def _build_chat_workspace():
    if ui_state.current_page != "research":
        return

    with ui.column().classes("flex-1 panel gap-3 h-full flex flex-col justify-between overflow-hidden p-4 relative"):
        # Central Chat Thread (Scrollable Area)
        with ui.scroll_area().classes("w-full flex-1 px-2 overflow-y-auto border-0") as chat_scroll:
            ui_state.chat_container = ui.column().classes("w-full gap-4 max-w-3xl mx-auto py-2")
            with ui_state.chat_container:
                # Welcome Card
                with ui.column().classes("w-full gap-2 p-6 bg-gradient-to-r from-indigo-950/40 to-purple-950/40 rounded-2xl border border-indigo-500/20 text-center items-center justify-center my-6 shadow-xl"):
                    ui.label("🤖 KhabriChacha AI Research").classes("text-xl font-bold text-indigo-200 tracking-wide")
                    ui.markdown(
                        "Ask any question or research mission. **LLM-1** routes the query & selects tools; **LLM-2** analyzes evidence & synthesizes answers."
                    ).classes("text-sm text-gray-300 max-w-md")

        # Execution Progress Line
        ui_state.progress_bar = ui.linear_progress(value=0.0).classes("w-full rounded h-1 flex-shrink-0 my-1")

        # Docked Bottom Prompt Bar (Perplexity / ChatGPT Style)
        with ui.column().classes("w-full bg-gray-900/90 rounded-2xl border border-gray-700/80 p-3 gap-2 shadow-2xl flex-shrink-0 max-w-3xl mx-auto"):
            with ui.row().classes("w-full items-center gap-2 justify-between border-b border-gray-800/80 pb-1.5 px-1"):
                with ui.row().classes("items-center gap-2"):
                    ui_state.strategy_select = ui.select(
                        options=["Auto (Recommended)", "Deep Research"],
                        value="Auto (Recommended)",
                    ).props("dense options-dense borderless").classes("bg-gray-800 text-xs text-indigo-300 rounded px-2 py-0.5 border border-indigo-500/30")

                    ui_state.sources_input = ui.number(
                        value=5, min=1, max=20,
                        prefix="Sources: "
                    ).props("dense borderless").classes("w-28 bg-gray-800 text-xs text-gray-300 rounded px-2 py-0.5 border border-gray-700")

                with ui.row().classes("items-center gap-1"):
                    ui.button("Pause", on_click=pause_research).props("dense flat color=gray text-xs")
                    ui.button("Stop", on_click=stop_research).props("dense flat color=red text-xs")
                    ui_state.save_project_btn = ui.button("Save", on_click=save_project_clicked).props("dense flat color=indigo-4 text-xs").props("disable")

            with ui.row().classes("w-full items-center gap-2 pt-1 px-1"):
                ui_state.goal_input = ui.textarea(
                    placeholder="Ask anything or define a research mission..."
                ).classes("flex-1 bg-transparent text-gray-100 text-sm border-0 focus:outline-none resize-none px-2").props("rows=1 autogrow")
                
                ui.button(
                    "Research", icon="send",
                    on_click=run_research_clicked
                ).classes("control-btn px-5 py-2 text-sm font-semibold rounded-xl shadow-lg")



def _build_right_panel():
    if ui_state.current_page != "research":
        return
    with ui.column().classes("w-[280px] flex-shrink-0 gap-3 h-full overflow-hidden"):
        _build_tabbed_workspace()


def _build_tabbed_workspace():
    with ui.element("div").classes("panel flex-1 flex flex-col h-full overflow-hidden"):
        with ui.tabs().classes("w-full") as tabs:
            tab_results = ui.tab("Trace", icon="analytics")
            tab_downloads = ui.tab("Downloads", icon="download")
            tab_logs = ui.tab("Logs", icon="terminal")

        with ui.tab_panels(tabs, value=tab_results).classes("w-full flex-1 overflow-y-auto"):
            with ui.tab_panel(tab_results):
                with ui.column().classes("w-full gap-2 text-xs"):
                    ui.html('<div class="text-indigo-400 font-bold uppercase tracking-wider text-[10px]">Dual Model Execution Trace</div>')
                    ui_state.strategy_indicator = ui.label("Strategy: —").classes("text-indigo-300 font-semibold")
                    ui_state.confidence_indicator = ui.label("Confidence: —").classes("text-gray-400")
                    ui_state.latency_indicator = ui.label("Est. Time: —").classes("text-gray-400")
                    ui_state.cost_indicator = ui.label("Est. Cost: —").classes("text-gray-400")
                    
                    ui.html('<hr class="border-gray-800 my-1">')
                    ui.html('<div class="text-indigo-400 font-bold uppercase tracking-wider text-[10px]">Pipeline Gates</div>')
                    ui_state.planner_indicator = ui.label("LLM-1 Router: —")
                    ui_state.search_indicator = ui.label("Search Engine: —")
                    ui_state.reasoning_indicator = ui.label("LLM-2 Analysis: —")
                    ui_state.evidence_indicator = ui.label("Grounding: —")
                    ui_state.report_indicator = ui.label("Report Gen: —")

                    ui.html('<hr class="border-gray-800 my-1">')
                    ui.html('<div class="text-indigo-400 font-bold uppercase tracking-wider text-[10px]">Retrieval & Consensus</div>')
                    ui_state.sources_found_indicator = ui.label("Sources Found: —")
                    ui_state.sources_selected_indicator = ui.label("Sources Used: —")
                    ui_state.duplicates_removed_indicator = ui.label("Deduplicated: —")
                    ui_state.trust_score_indicator = ui.label("Avg Trust Score: —")
                    ui_state.consensus_score_indicator = ui.label("Numeric Consensus: —")

            with ui.tab_panel(tab_downloads):
                ui_state.downloads_container = ui.column().classes("w-full gap-2")
                with ui_state.downloads_container:
                    ui.markdown("_No report files available yet._").classes("text-xs text-gray-400")

            with ui.tab_panel(tab_logs):
                ui_state.log_view = ui.log().classes("w-full log-view h-80")


