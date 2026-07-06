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

# Hook up event bus to UI
def handle_event(event):
    if event.level == "INFO":
        if event.component == "Controller" and ui_state.progress_label:
            ui_state.progress_label.set_text(event.message)
            
_event_bus.subscribe("INFO", handle_event)
_event_bus.subscribe("WARNING", handle_event)
_event_bus.subscribe("ERROR", handle_event)

async def run_research(goal: str, model: str, depth: str, sources: int):
    logger.info(f"Starting research: goal='{goal}', model='{model}', depth={depth}, sources={sources}")
    
    if not goal or not goal.strip():
        ui.notify("Please enter a research mission objective.", type="warning")
        return

    if not model:
        ui.notify("Please select a model before running.", type="warning")
        return

    # Parse provider/model from UI selector (e.g. "gemini/gemini-1.5-pro")
    provider, model_name = _provider_manager.parse_ui_option(model)
    
    request = ResearchRequest(
        mission=goal,
        provider=provider,
        model=model_name,
        depth=depth.lower(),
        max_iterations=5,
        workspace=str(_workspace_manager.root),
        metadata={"max_sources": sources}
    )

    # Update UI state to Running
    if ui_state.status_label:
        ui_state.status_label.set_text("Running")
        ui_state.status_label.classes(replace="status-badge status-running")
    if ui_state.model_label:
        ui_state.model_label.set_text(model)
    if ui_state.project_label:
        ui_state.project_label.set_text("Research Mission")
    if ui_state.progress_bar:
        ui_state.progress_bar.set_value(0.5)  # Indeterminate for now
    if ui_state.progress_label:
        ui_state.progress_label.set_text("Starting research...")

    # Run research pipeline in background thread
    try:
        result = await run.io_bound(_research_controller.start_research, request)
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        result = None

    # Update UI based on results
    if result and result.success:
        # Load report markdown
        if result.report_md_path:
            import os
            if os.path.exists(result.report_md_path):
                with open(result.report_md_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                if ui_state.results_markdown:
                    ui_state.results_markdown.set_content(md_content)
                    
        # Load references from ProjectManager
        try:
            pm = _workspace_manager.get_project(result.project_id)
            refs = pm.load_references()
            if ui_state.references_markdown and refs.entries:
                lines = [f"- [{r.title}]({r.url})" for r in refs.entries if r.url]
                ui_state.references_markdown.set_content("\n".join(lines) if lines else "_No references._")
        except Exception:
            pass
            
        ui.notify(f"Research completed in {result.elapsed_time:.1f}s", type="positive")
    else:
        error_msg = "\n".join([e.message for e in result.errors]) if result else "Unknown error"
        if ui_state.results_markdown:
            ui_state.results_markdown.set_content(f"Research failed:\n\n{error_msg}")
        ui.notify("Research failed", type="negative")

    # Restore status Ready
    if ui_state.status_label:
        ui_state.status_label.set_text("Ready")
        ui_state.status_label.classes(replace="status-badge status-ready")
    if ui_state.progress_bar:
        ui_state.progress_bar.set_value(1.0)
    if ui_state.progress_label:
        ui_state.progress_label.set_text("Completed")


async def run_research_clicked():
    logger.info(f"goal_input ref: {ui_state.goal_input}")
    if ui_state.goal_input:
        logger.info(f"goal_input value directly: '{ui_state.goal_input.value}'")
    goal = ui_state.goal_input.value if ui_state.goal_input else ""
    model = ui_state.model_select.value if ui_state.model_select else "openai/gpt-4o"
    depth = ui_state.depth_select.value if ui_state.depth_select else "Standard"
    sources = int(ui_state.sources_input.value) if ui_state.sources_input else 5
    
    await run_research(goal, model, depth, sources)


def pause_research():
    logger.info("Research paused.")


def resume_research():
    logger.info("Research resumed.")


def stop_research():
    logger.info("Research stopped.")


def load_project(project_id: str):
    """Load a saved project's report and references into the UI."""
    logger.info(f"Loading project: {project_id}")
    try:
        manifest = _workspace_manager.get_project(project_id).manifest
        pm = _workspace_manager.get_project(project_id)

        # Load report markdown
        import os
        report_path = os.path.join(pm.project_path, "report.md")
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            if ui_state.results_markdown and md_content.strip():
                ui_state.results_markdown.set_content(md_content)

        # Load references
        refs = pm.load_references()
        if ui_state.references_markdown and refs.entries:
            lines = [f"- [{r.title}]({r.url})" for r in refs.entries if r.url]
            ui_state.references_markdown.set_content("\n".join(lines) if lines else "_No references._")

        # Update status bar
        if ui_state.project_label:
            ui_state.project_label.set_text(manifest.title or project_id)
        if ui_state.model_label:
            ui_state.model_label.set_text(f"{manifest.provider}/{manifest.model}" if manifest.provider else "N/A")

        ui.notify(f"Loaded project: {manifest.title}", type="info")
    except Exception as e:
        logger.error(f"Failed to load project {project_id}: {e}")
        ui.notify(f"Failed to load project: {e}", type="negative")
