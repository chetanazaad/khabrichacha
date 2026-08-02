from loguru import logger
import asyncio
from nicegui import ui, run
import khabrichacha.ui.ui_state as ui_state

from deployment.config_loader import load_config
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.providers.provider_manager import ProviderManager
from deployment.runtime.event_bus import EventBus
from deployment.runtime.research_controller import ResearchController
from deployment.runtime.models.research_request import ResearchRequest

# Global controller state
_config = load_config()
_workspace_manager = WorkspaceManager(_config.workspace.root)
_provider_manager = ProviderManager(_config.model_dump())
_event_bus = EventBus()
_research_controller = ResearchController(_workspace_manager, _provider_manager, _event_bus)

# Hook up event bus to UI safely
def handle_event(event):
    msg = f"[{event.component}] {event.message}"
    if ui_state.log_view:
        try:
            ui_state.log_view.push(msg)
        except Exception:
            ui_state.log_view = None
            
    if event.level == "INFO":
        if event.component == "Controller" and ui_state.progress_label:
            try:
                ui_state.progress_label.set_text(event.message)
            except Exception:
                ui_state.progress_label = None
            
_event_bus.subscribe("INFO", handle_event)
_event_bus.subscribe("WARNING", handle_event)
_event_bus.subscribe("ERROR", handle_event)

_STRATEGY_MAP = {
    "Auto (Recommended)": None,
    "Deep Research": "DEEP_RESEARCH",
}

_DOWNLOAD_FORMATS = [
    # (attribute on ResearchResult, filename, display label, icon)
    ("report_pdf_path", "report.pdf", "PDF", "picture_as_pdf"),
    ("report_docx_path", "report.docx", "Word (.docx)", "description"),
    ("report_md_path", "report.md", "Markdown", "article"),
    ("report_txt_path", "report.txt", "Text (.txt)", "notes"),
    ("report_json_path", "report.json", "JSON", "data_object"),
]


def navigate_to_page(page_name: str):
    ui_state.current_page = page_name.lower()
    ui.notify(f"Switched to {page_name} view", type="info")
    from khabrichacha.ui.components import render_workspace_view, _render_sidebar_content
    render_workspace_view()
    _render_sidebar_content.refresh()


def toggle_sidebar():
    ui_state.sidebar_visible = not ui_state.sidebar_visible
    if ui_state.sidebar_container:
        if ui_state.sidebar_visible:
            ui_state.sidebar_container.classes(remove="collapsed")
        else:
            ui_state.sidebar_container.classes(add="collapsed")


def start_new_chat():
    ui_state.current_page = "research"
    ui_state.current_project_id = None
    if ui_state.project_label:
        ui_state.project_label.set_text("New Chat")
    if ui_state.save_project_btn:
        ui_state.save_project_btn.props("disable")

    from khabrichacha.ui.components import render_workspace_view, _render_sidebar_content
    render_workspace_view()
    _render_sidebar_content.refresh()
    _populate_downloads(None)
    ui.notify("Started new research session", type="positive")


def refresh_saved_projects_sidebar():
    from khabrichacha.ui.components import _render_sidebar_content
    _render_sidebar_content.refresh()



def _populate_downloads(project_path: "str | None" = None, result=None):
    """
    Refill the Downloads tab with real download buttons for whichever
    report files actually exist for this run/project. Previously this tab
    was a hardcoded "No downloads available" placeholder with no logic
    behind it at all, even though ReportExporter was already generating
    PDF/Word/Markdown/JSON files that nothing in the UI ever exposed.
    """
    if not ui_state.downloads_container:
        return

    import os

    try:
        ui_state.downloads_container.clear()
        with ui_state.downloads_container:
            found_any = False
            for attr, filename, label, icon in _DOWNLOAD_FORMATS:
                path = getattr(result, attr, "") if result is not None else ""
                if not path and project_path:
                    candidate = os.path.join(project_path, filename)
                    if os.path.exists(candidate):
                        path = candidate
                if path and os.path.exists(path):
                    found_any = True
                    with ui.row().classes("w-full items-center justify-between p-2 bg-gray-800 rounded"):
                        ui.label(label).classes("text-sm text-gray-200")
                        ui.button(
                            "Download", icon=icon,
                            on_click=lambda p=path, f=filename: ui.download(p, filename=f)
                        ).props("flat dense color=indigo-4")
            if not found_any:
                ui.markdown("_No downloads available yet — run a research mission first._").classes("results-panel text-sm")
    except RuntimeError:
        ui_state.downloads_container = None
    except Exception as e:
        logger.warning(f"Could not populate downloads: {e}")


async def run_research(goal: str, router_model_opt: str, analysis_model_opt: str, strategy_name: str, sources: int):
    logger.info(f"Starting dual-model research: goal='{goal}', router='{router_model_opt}', analysis='{analysis_model_opt}', strategy={strategy_name}, sources={sources}")
    
    if not goal or not goal.strip():
        ui.notify("Please enter a research query.", type="warning")
        return

    # Render User Chat Message Bubble
    if ui_state.chat_container:
        with ui_state.chat_container:
            with ui.row().classes("w-full gap-3 items-start justify-end my-2"):
                with ui.column().classes("bg-indigo-600/30 text-indigo-100 rounded-2xl px-4 py-3 max-w-2xl border border-indigo-500/30 shadow-lg"):
                    ui.label(goal).classes("text-sm font-medium whitespace-pre-wrap")
                ui.label("👤").classes("text-xl")

    # Render Assistant Loading Bubble
    assistant_md = None
    if ui_state.chat_container:
        with ui_state.chat_container:
            with ui.row().classes("w-full gap-3 items-start my-2"):
                ui.label("🤖").classes("text-xl")
                with ui.column().classes("bg-gray-900/90 rounded-2xl p-4 flex-1 border border-gray-700/80 shadow-lg gap-2"):
                    with ui.row().classes("items-center gap-2 text-xs text-indigo-400 font-mono border-b border-gray-800 pb-2 w-full"):
                        ui.spinner(size="xs").classes("text-indigo-400")
                        ui.label(f"Routing query with LLM-1 ({router_model_opt.split('/')[-1]})...").classes("font-semibold")
                    assistant_md = ui.markdown("_Analyzing request and planning execution..._").classes("text-sm text-gray-200")

    # Evaluate cost and strategy before executing
    from deployment.runtime.intelligence.cost_estimator import CostEstimator
    from deployment.runtime.query_classifier import QueryClassifier
    qc = QueryClassifier()
    pre_strategy = qc.classify(goal, _STRATEGY_MAP.get(strategy_name))
    pre_est = CostEstimator().estimate(pre_strategy)
    
    if ui_state.latency_indicator:
        ui_state.latency_indicator.set_text(f"Est. Time: {pre_est['estimated_latency_seconds']}s")
    if ui_state.cost_indicator:
        ui_state.cost_indicator.set_text(f"Est. Cost: {pre_est['cost_category']}")

    # Parse provider/model from UI selectors
    ing_provider, ing_model = _provider_manager.parse_ui_option(router_model_opt)
    ana_provider, ana_model = _provider_manager.parse_ui_option(analysis_model_opt)
    
    request = ResearchRequest(
        mission=goal,
        provider=ana_provider,
        model=ana_model,
        ingestion_provider=ing_provider,
        ingestion_model=ing_model,
        analysis_provider=ana_provider,
        analysis_model=ana_model,
        depth="standard",
        max_iterations=5,
        workspace=str(_workspace_manager.root),
        strategy_override=_STRATEGY_MAP.get(strategy_name),
        metadata={"max_sources": sources}
    )

    # Update UI state to Running
    if ui_state.status_label:
        ui_state.status_label.set_text("Running")
        ui_state.status_label.classes(replace="status-badge status-running")
    if ui_state.progress_bar:
        ui_state.progress_bar.set_value(0.5)
    if ui_state.progress_label:
        ui_state.progress_label.set_text(f"Executing tools with {request.ingestion_model}...")

    # Run research pipeline in background thread
    try:
        result = await run.io_bound(_research_controller.start_research, request)
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        result = None

    # Update UI based on results
    if result and result.success:
        escalation_banner = ""
        if result.statistics.escalation_history:
            notes = []
            for e in result.statistics.escalation_history:
                notes.append(
                    f"- Escalated from **{e['from_strategy']}** to **{e['to_strategy']}** "
                    f"(quality score {e['overall_score']:.0f}/100, below {e['threshold']:.0f} threshold)."
                )
            escalation_banner = "> **Note:** " + "\n".join(notes) + "\n\n"

        content_text = ""
        if result.direct_answer:
            content_text = escalation_banner + result.direct_answer
        elif result.report_md_path:
            import os
            if os.path.exists(result.report_md_path):
                with open(result.report_md_path, 'r', encoding='utf-8') as f:
                    content_text = escalation_banner + f.read()

        if assistant_md and content_text:
            assistant_md.set_content(content_text)

        ui_state.current_project_id = result.project_id
        _populate_downloads(result.project_path, result)
        refresh_saved_projects_sidebar()

        if result.project_id and result.project_id.startswith("temp_session_"):
            if ui_state.save_project_btn:
                ui_state.save_project_btn.props(remove="disable")

        # Update trace indicators
        if ui_state.strategy_indicator:
            ui_state.strategy_indicator.set_text(f"Strategy: {result.strategy_used}")
        if ui_state.confidence_indicator:
            ui_state.confidence_indicator.set_text(f"Confidence: {result.strategy_confidence:.0%}")
        if ui_state.latency_indicator:
            ui_state.latency_indicator.set_text(f"Latency: {result.elapsed_time:.1f}s")
        if ui_state.cost_indicator:
            ui_state.cost_indicator.set_text(f"Router: {ing_model} | Analysis: {ana_model}")

        def set_ind(lbl, name, val):
            if lbl:
                status = "✔" if val else "✗"
                lbl.set_text(f"{name}: {status}")

        set_ind(ui_state.planner_indicator, "LLM-1 Router", True)
        set_ind(ui_state.search_indicator, "Search Engine", True)
        set_ind(ui_state.reasoning_indicator, "LLM-2 Analysis", True)
        set_ind(ui_state.evidence_indicator, "Grounding", True)
        set_ind(ui_state.report_indicator, "Report Gen", True)

        if ui_state.sources_found_indicator:
            ui_state.sources_found_indicator.set_text(f"Sources Found: {result.source_count}")
        if ui_state.sources_selected_indicator:
            ui_state.sources_selected_indicator.set_text(f"Sources Used: {result.source_count}")

        ui.notify(f"Research completed in {result.elapsed_time:.1f}s", type="positive")
    else:
        error_msg = "\n".join([e.message for e in result.errors]) if result else "Unknown execution error"
        if assistant_md:
            assistant_md.set_content(f"**Research execution failed:**\n\n{error_msg}")
        ui.notify("Research failed", type="negative")

    # Restore status Ready
    if ui_state.status_label:
        ui_state.status_label.set_text("Ready")
        ui_state.status_label.classes(replace="status-badge status-ready")
    if ui_state.progress_bar:
        ui_state.progress_bar.set_value(1.0)
    if ui_state.progress_label:
        ui_state.progress_label.set_text("Research completed")


async def run_research_clicked():
    goal = ""
    if ui_state.goal_input:
        if ui_state.goal_input.value and str(ui_state.goal_input.value).strip():
            goal = str(ui_state.goal_input.value).strip()
        else:
            try:
                dom_val = await ui.run_javascript(
                    f"document.querySelector('#c{ui_state.goal_input.id} textarea')?.value || document.querySelector('#c{ui_state.goal_input.id}')?.value || document.querySelector('textarea')?.value || ''"
                )
                if dom_val and str(dom_val).strip():
                    goal = str(dom_val).strip()
            except Exception:
                pass

    if not goal:
        ui.notify("Please enter a research query.", type="warning")
        return


    router_opt = ui_state.router_model_select.value if ui_state.router_model_select else "gemini/gemini-2.0-flash"
    analysis_opt = ui_state.analysis_model_select.value if ui_state.analysis_model_select else "gemini/gemini-2.0-pro"
    strategy_name = ui_state.strategy_select.value if ui_state.strategy_select else "Auto (Recommended)"
    sources = int(ui_state.sources_input.value) if ui_state.sources_input else 5

    # Clear input after obtaining non-empty value
    if ui_state.goal_input:
        ui_state.goal_input.value = ""

    await run_research(goal, router_opt, analysis_opt, strategy_name, sources)




def save_project_clicked():
    if not ui_state.current_project_id:
        ui.notify("No active research session to save.", type="warning")
        return
        
    try:
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(_workspace_manager)
        if ui_state.current_project_id.startswith("temp_session_"):
            pm.promote_session_to_project(ui_state.current_project_id)
            ui.notify("Project successfully saved!", type="positive")
            if ui_state.save_project_btn:
                ui_state.save_project_btn.props("disable")
            refresh_saved_projects_sidebar()
        else:
            ui.notify("Project is already saved permanently.", type="info")
    except Exception as e:
        logger.error(f"Failed to promote session: {e}")
        ui.notify(f"Failed to save project: {e}", type="negative")


def pause_research():
    logger.info("Research paused.")


def resume_research():
    logger.info("Research resumed.")


def stop_research():
    logger.info("Research stopped.")


def load_project(project_id: str):
    """Load a saved project's report and prompt directly into the Chat UI thread."""
    logger.info(f"Loading project into Chat UI: {project_id}")
    try:
        ui_state.current_page = "research"
        ui_state.current_project_id = project_id

        from khabrichacha.ui.components import render_workspace_view
        render_workspace_view()

        manifest = _workspace_manager.get_project(project_id).manifest
        pm = _workspace_manager.get_project(project_id)

        import os
        report_path = os.path.join(pm.project_path, "report.md")
        md_content = ""
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                md_content = f.read()

        # Update Chat Thread Container with User & Assistant Bubbles
        if ui_state.chat_container:
            ui_state.chat_container.clear()
            with ui_state.chat_container:
                # User Prompt Bubble
                prompt_title = manifest.title or project_id
                with ui.row().classes("w-full gap-3 items-start justify-end my-2"):
                    with ui.column().classes("bg-indigo-600/30 text-indigo-100 rounded-2xl px-4 py-3 max-w-2xl border border-indigo-500/30 shadow-lg"):
                        ui.label(prompt_title).classes("text-sm font-medium whitespace-pre-wrap")
                    ui.label("👤").classes("text-xl")

                # Assistant Report Bubble
                with ui.row().classes("w-full gap-3 items-start my-2"):
                    ui.label("🤖").classes("text-xl")
                    with ui.column().classes("bg-gray-900/90 rounded-2xl p-4 flex-1 border border-gray-700/80 shadow-lg gap-2"):
                        with ui.row().classes("items-center gap-2 text-xs text-indigo-400 font-mono border-b border-gray-800 pb-2 w-full justify-between"):
                            ui.label(f"Project: {project_id[:16]}").classes("font-semibold")
                            ui.label(f"Created: {manifest.created_at or ''}").classes("text-gray-400 text-[10px]")
                        if md_content.strip():
                            ui.markdown(md_content).classes("text-sm text-gray-200")
                        else:
                            ui.markdown("_No report markdown file found for this session._").classes("text-sm text-gray-400 italic")

        # Update Header Title
        if ui_state.project_label:
            ui_state.project_label.set_text(manifest.title or project_id)

        # Populate Downloads Panel for this project
        _populate_downloads(pm.project_path)

        ui.notify(f"Loaded project: {manifest.title or project_id}", type="info")
    except Exception as e:
        logger.error(f"Failed to load project {project_id}: {e}")
        ui.notify(f"Failed to load project: {e}", type="negative")

