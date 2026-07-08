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
    msg = f"[{event.component}] {event.message}"
    if ui_state.log_view:
        ui_state.log_view.push(msg)
    if ui_state.progress_label:
        ui_state.progress_label.set_text(event.message)
    if hasattr(event, "metadata") and isinstance(event.metadata, dict):
        prog = event.metadata.get("progress")
        if prog is not None and ui_state.progress_bar:
            ui_state.progress_bar.set_value(float(prog))
            
_event_bus.subscribe("INFO", handle_event)
_event_bus.subscribe("WARNING", handle_event)
_event_bus.subscribe("ERROR", handle_event)

_STRATEGY_MAP = {
    "Auto (Recommended)": None,
    "Fast Answer": "FAST",
    "Lookup": "LOOKUP",
    "Structured Data": "STRUCTURED",
    "Comparison": "COMPARISON",
    "Analysis": "ANALYSIS",
    "Research": "RESEARCH",
    "Deep Research": "DEEP_RESEARCH",
}

async def run_research(goal: str, model: str, strategy_name: str, sources: int):
    logger.info(f"Starting research: goal='{goal}', model='{model}', strategy={strategy_name}, sources={sources}")
    
    if not goal or not goal.strip():
        ui.notify("Please enter a research mission objective.", type="warning")
        return

    if not model:
        ui.notify("Please select a model before running.", type="warning")
        return

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
        
    if pre_est['cost_category'] == "High":
        ui.notify("Warning: This query may consume a high number of tokens.", type="warning", timeout=3000)

    # Parse provider/model from UI selector (e.g. "gemini/gemini-1.5-pro")
    provider, model_name = _provider_manager.parse_ui_option(model)
    
    request = ResearchRequest(
        mission=goal,
        provider=provider,
        model=model_name,
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
        # Load direct answer or report markdown
        if result.direct_answer:
            if ui_state.results_markdown:
                ui_state.results_markdown.set_content(result.direct_answer)
        elif result.report_md_path:
            import os
            if os.path.exists(result.report_md_path):
                with open(result.report_md_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                if ui_state.results_markdown:
                    ui_state.results_markdown.set_content(md_content)
                    
        # Load references from ProjectManager
        try:
            if result.project_id:
                pm = _workspace_manager.get_project(result.project_id)
                refs = pm.load_references()
                if ui_state.references_markdown and refs.entries:
                    lines = [f"- [{r.title}]({r.url})" for r in refs.entries if r.url]
                    ui_state.references_markdown.set_content("\n".join(lines) if lines else "_No references._")
        except Exception:
            pass

        # Store current project ID in UI state
        ui_state.current_project_id = result.project_id
        
        # Enable/disable Save Project button based on temporary session status
        if result.project_id and result.project_id.startswith("temp_session_"):
            if ui_state.save_project_btn:
                ui_state.save_project_btn.props(remove="disable")
        else:
            if ui_state.save_project_btn:
                ui_state.save_project_btn.props("disable")

        # Update strategy and retrieval indicators
        task_types = {
            "FAST": ("Direct Q&A", "Instant LLM Answering"),
            "LOOKUP": ("Simple Lookup", "Retrieval & Formatting"),
            "STRUCTURED": ("Data Extraction", "Tabular Extraction"),
            "COMPARISON": ("Entity Comparison", "Parallel Retrieval & Comparison"),
            "ANALYSIS": ("Deep Analysis", "Synthesis & Evaluation"),
            "RESEARCH": ("Full Research", "Planner & Orchestrated Research"),
            "DEEP_RESEARCH": ("Deep Investigation", "Planner & Iterative Evidence Research")
        }
        task_type, exec_mode = task_types.get(result.strategy_used, ("General Q&A", "Standard Answering"))

        if ui_state.strategy_indicator:
            ui_state.strategy_indicator.set_text(f"Task Type: {task_type} | Execution Mode: {exec_mode}")
        if ui_state.confidence_indicator:
            ui_state.confidence_indicator.set_text(f"Confidence: {result.strategy_confidence:.0%}")
        if ui_state.latency_indicator:
            ui_state.latency_indicator.set_text(f"Est. Time: {result.elapsed_time:.1f}s")
        if ui_state.cost_indicator:
            ui_state.cost_indicator.set_text(f"Model: {result.model} | Provider: {result.provider}")
            
        # Pipeline indicators
        from deployment.runtime.query_classifier import QueryClassifier
        qc = QueryClassifier()
        rules = qc.rules.get("strategies", {}).get(result.strategy_used, {})
        
        def set_ind(lbl, name, val):
            if lbl:
                status = "✔" if val else "✗"
                lbl.set_text(f"{name}: {status}")
                if val:
                    lbl.classes(replace="text-green-400")
                else:
                    lbl.classes(replace="text-red-400")

        set_ind(ui_state.planner_indicator, "Planner", rules.get("requires_planner", False))
        set_ind(ui_state.search_indicator, "Search", rules.get("requires_search", False))
        set_ind(ui_state.reasoning_indicator, "Reasoning", rules.get("requires_reasoning", False))
        set_ind(ui_state.evidence_indicator, "Evidence", rules.get("requires_evidence_evaluation", False))
        set_ind(ui_state.report_indicator, "Report", rules.get("requires_report_generation", False))
        set_ind(ui_state.project_indicator, "Project", rules.get("allow_project_creation", False))

        # Retrieval/consensus indicators
        if ui_state.sources_found_indicator:
            ui_state.sources_found_indicator.set_text(f"Found: {result.source_count}")
        if ui_state.sources_selected_indicator:
            ui_state.sources_selected_indicator.set_text(f"Selected: {result.source_count}")
        if ui_state.duplicates_removed_indicator:
            ui_state.duplicates_removed_indicator.set_text("Duplicates: 0")
        if ui_state.trust_score_indicator:
            avg_trust = result.retrieval_stats.get("avg_trust_score", 85)
            ui_state.trust_score_indicator.set_text(f"Avg Trust: {avg_trust:.0f}")
        if ui_state.output_format_indicator:
            ui_state.output_format_indicator.set_text(f"Format: {result.output_format or 'Text'}")
        if ui_state.knowledge_cache_indicator:
            ui_state.knowledge_cache_indicator.set_text(f"Cache Hits: {result.statistics.knowledge_cache_hits}")
        if ui_state.consensus_score_indicator:
            consensus = result.retrieval_stats.get("consensus_score")
            if consensus:
                ui_state.consensus_score_indicator.set_text(f"Consensus: {consensus:.0%}")
            else:
                ui_state.consensus_score_indicator.set_text("Consensus: N/A")
            
        # Update downloads panel
        if result.project_id:
            update_downloads(result.project_id)
            
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


def update_downloads(project_id: str):
    if ui_state.downloads_container:
        ui_state.downloads_container.clear()
        import os
        from pathlib import Path
        
        files_found = []
        try:
            # Check temp or projects path
            if project_id.startswith("temp_session_"):
                project_dir = _workspace_manager.temp / project_id
            else:
                project_dir = _workspace_manager.get_project_path(project_id)
                
            for name, label in [("report.pdf", "Download PDF Report"), 
                                ("report.docx", "Download Word DOCX Report"), 
                                ("report.md", "Download Markdown Report"),
                                ("report.json", "Download JSON Metadata")]:
                fpath = project_dir / name
                if fpath.exists():
                    files_found.append((fpath, label))
        except Exception as e:
            logger.warning(f"Error finding files in project dir for {project_id}: {e}")
            
        if files_found:
            with ui_state.downloads_container:
                ui.markdown("### Available Deliverables").classes("text-lg font-bold mb-2 text-slate-200")
                for fpath, label in files_found:
                    def make_click(p=fpath):
                        ui.download(str(p))
                    ui.button(label, on_click=make_click, icon="file_download").classes("w-full md:w-auto bg-primary text-white")
        else:
            with ui_state.downloads_container:
                ui.markdown("_No deliverables generated for this session yet._").classes("results-panel text-sm")


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
            update_downloads(ui_state.current_project_id)
        else:
            ui.notify("Project is already saved permanently.", type="info")
    except Exception as e:
        logger.error(f"Failed to promote session: {e}")
        ui.notify(f"Failed to save project: {e}", type="negative")


async def run_research_clicked():
    # Force-sync the textarea value from the browser before reading
    if ui_state.goal_input:
        try:
            val = await ui.run_javascript(
                f"document.querySelector('[id=\"c{ui_state.goal_input.id}\"] textarea')?.value ?? ''"
            )
            if val:
                ui_state.goal_input.value = val
        except Exception:
            pass

    goal = ui_state.goal_input.value if ui_state.goal_input else ""
    model = ui_state.model_select.value if ui_state.model_select else "openai/gpt-4o"
    strategy_name = ui_state.strategy_select.value if ui_state.strategy_select else "Auto (Recommended)"
    sources = int(ui_state.sources_input.value) if ui_state.sources_input else 5
    
    await run_research(goal, model, strategy_name, sources)


def pause_research():
    logger.info("Research paused.")


def resume_research():
    logger.info("Research resumed.")


def stop_research():
    logger.info("Research stopped.")
    _research_controller.stop()
    ui.notify("Stopping active research...", type="warning")


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

        # Update downloads
        update_downloads(project_id)

        # Update status bar
        if ui_state.project_label:
            ui_state.project_label.set_text(manifest.title or project_id)
        if ui_state.model_label:
            ui_state.model_label.set_text(f"{manifest.provider}/{manifest.model}" if manifest.provider else "N/A")

        ui.notify(f"Loaded project: {manifest.title}", type="info")
    except Exception as e:
        logger.error(f"Failed to load project {project_id}: {e}")
        ui.notify(f"Failed to load project: {e}", type="negative")
