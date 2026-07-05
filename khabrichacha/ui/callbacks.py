from loguru import logger
import asyncio
from nicegui import ui, run
import khabrichacha.ui.ui_state as ui_state
from khabrichacha.core.session import Session
from khabrichacha.llm.manager import LLMManager
from khabrichacha.tools.registry import ToolRegistry
from khabrichacha.core.orchestrator import Orchestrator


async def run_research(goal: str, model: str, depth: str, sources: int):
    logger.info(f"Starting research: goal='{goal}', model='{model}', depth={depth}, sources={sources}")
    
    if not goal or not goal.strip():
        ui.notify("Please enter a research mission objective.", type="warning")
        return

    if not model:
        ui.notify("Please select a model before running.", type="warning")
        return

    # Create Session
    session = Session()

    # Configure session based on UI inputs
    model_mapping = {
        "gpt-4": ("openai", "gpt-4"),
        "gpt-3.5-turbo": ("openai", "gpt-3.5-turbo"),
        "gemini-pro": ("gemini", "gemini-1.5-pro"),
        "claude-3": ("openai", "gpt-4"),
        "ollama/llama3": ("ollama", "llama3"),
    }
    provider, model_name = model_mapping.get(model, ("openai", model))
    
    session.config["llm"] = {
        "default_provider": provider,
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    if "providers" not in session.config:
        session.config["providers"] = {}
    session.config["providers"][provider] = {
        "model": model_name,
    }
    
    session.config["research"] = {
        "depth": depth.lower(),
        "max_sources": sources,
    }

    # Create LLMManager
    llm_manager = LLMManager(session.config)

    # Create ToolRegistry
    tool_registry = ToolRegistry()

    # Create Orchestrator
    orchestrator = Orchestrator(session, llm_manager, tool_registry)

    # Update UI state to Running
    if ui_state.status_label:
        ui_state.status_label.set_text("Running")
        ui_state.status_label.classes(replace="status-badge status-running")
    if ui_state.model_label:
        ui_state.model_label.set_text(model)
    if ui_state.project_label:
        ui_state.project_label.set_text("Research Mission")
    if ui_state.progress_bar:
        ui_state.progress_bar.set_value(0.0)
    if ui_state.progress_label:
        ui_state.progress_label.set_text("Planning research...")

    # Define periodic progress poller
    async def poll_progress():
        while session.state.status == "running":
            tasks = session.state.tasks
            if tasks:
                completed = sum(1 for t in tasks if t.status in ("completed", "failed"))
                progress_val = completed / len(tasks)
                if ui_state.progress_bar:
                    ui_state.progress_bar.set_value(progress_val)
                if ui_state.progress_label:
                    ui_state.progress_label.set_text(f"Step {completed} of {len(tasks)}")
            await asyncio.sleep(0.5)

    # Run research pipeline in background thread
    polling_task = asyncio.create_task(poll_progress())
    try:
        result = await run.io_bound(orchestrator.run, goal)
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        result = {"success": False, "report": f"Error during execution: {e}"}
    finally:
        polling_task.cancel()

    # Display report markdown
    if ui_state.results_markdown:
        if result and result.get("success"):
            ui_state.results_markdown.set_content(result.get("report", ""))
        else:
            ui_state.results_markdown.set_content(f"Research failed:\n\n{result.get('report') if result else 'Unknown error'}")

    # Display references
    if ui_state.references_markdown:
        ui_state.references_markdown.set_content(extract_references(session))

    # Restore status Ready
    if ui_state.status_label:
        ui_state.status_label.set_text("Ready")
        ui_state.status_label.classes(replace="status-badge status-ready")
    if ui_state.progress_bar:
        ui_state.progress_bar.set_value(1.0)
    if ui_state.progress_label:
        ui_state.progress_label.set_text("Completed")


async def run_research_clicked():
    goal = ui_state.goal_input.value if ui_state.goal_input else ""
    model = ui_state.model_select.value if ui_state.model_select else "gpt-4"
    depth = ui_state.depth_select.value if ui_state.depth_select else "Standard"
    sources = int(ui_state.sources_input.value) if ui_state.sources_input else 5
    
    await run_research(goal, model, depth, sources)


def extract_references(session) -> str:
    import json
    sources = []
    seen_urls = set()
    for task in session.state.tasks:
        if task.status != "completed" or not task.result:
            continue
        res_str = task.result
        parsed_res = None
        if isinstance(res_str, str) and (
            (res_str.startswith("{") and res_str.endswith("}")) or 
            (res_str.startswith("[") and res_str.endswith("]"))
        ):
            try:
                parsed_res = json.loads(res_str)
            except Exception:
                pass
        if parsed_res is not None:
            if isinstance(parsed_res, list):
                for item in parsed_res:
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("name") or "Untitled Source"
                        url = item.get("url") or item.get("link") or ""
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            sources.append((title, url))
            elif isinstance(parsed_res, dict):
                if "url" in parsed_res:
                    url = parsed_res["url"]
                    title = parsed_res.get("title") or "Untitled Page"
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        sources.append((title, url))
    
    if not sources:
        return "_No references collected._"
    
    lines = []
    for title, url in sources:
        lines.append(f"- [{title}]({url})")
    return "\n".join(lines)


def pause_research():
    logger.info("Research paused.")


def resume_research():
    logger.info("Research resumed.")


def stop_research():
    logger.info("Research stopped.")


def load_project(name: str):
    logger.info(f"Loading project: {name}")
