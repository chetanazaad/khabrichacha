from nicegui import ui


def render_projects_view(on_load_project=None):
    """Render a card grid of all saved research projects."""
    with ui.column().classes("w-full h-full p-4 gap-4 overflow-y-auto"):
        with ui.row().classes("w-full items-center justify-between border-b border-gray-800 pb-2"):
            ui.label("Saved Projects & Research History").classes("text-lg font-bold text-indigo-300")
            ui.label("Click any project to load it into the chat workspace").classes("text-xs text-gray-400")

        try:
            from deployment.config_loader import load_config
            from deployment.workspace.workspace_manager import WorkspaceManager
            from deployment.workspace.project_manager import ProjectManager
            config = load_config()
            ws = WorkspaceManager(config.workspace.root)
            pm = ProjectManager(ws)
            projects = pm.list_projects()
        except Exception:
            projects = []

        if projects:
            with ui.grid(columns=2).classes("w-full gap-4"):
                for proj in projects:
                    title = proj.title or proj.project_id
                    with ui.column().classes("bg-gray-900/80 p-4 rounded-xl border border-gray-700/60 hover:border-indigo-500/50 transition-all gap-2 shadow-lg"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label(title[:30]).classes("font-bold text-sm text-indigo-200 truncate")
                            ui.label(proj.project_id[:12]).classes("text-[10px] font-mono text-gray-400 bg-gray-800 px-2 py-0.5 rounded")
                        
                        ui.label(f"Created: {proj.created_at or 'N/A'}").classes("text-xs text-gray-400")
                        
                        with ui.row().classes("w-full items-center justify-between mt-2 pt-2 border-t border-gray-800"):
                            if on_load_project:
                                ui.button("Open in Chat", icon="chat", on_click=lambda pid=proj.project_id: on_load_project(pid)).classes("control-btn text-xs px-3 py-1")
        else:
            with ui.column().classes("w-full p-8 text-center items-center justify-center bg-gray-900/40 rounded-xl border border-gray-800 gap-2"):
                ui.label("📂 No Saved Projects Found").classes("text-base font-bold text-gray-300")
                ui.label("Run research prompts and click 'Save' to archive your research history.").classes("text-xs text-gray-400")


def render_models_view():
    """Render LLM provider status and model capabilities."""
    with ui.column().classes("w-full h-full p-4 gap-4 overflow-y-auto"):
        with ui.row().classes("w-full items-center justify-between border-b border-gray-800 pb-2"):
            ui.label("LLM Engine & Provider Status").classes("text-lg font-bold text-indigo-300")
            ui.label("Available Local & Cloud Inference Models").classes("text-xs text-gray-400")

        try:
            from khabrichacha.providers.provider_manager import ProviderManager
            from deployment.config_loader import load_config
            config = load_config()
            pm = ProviderManager(config.model_dump())
            providers = pm.discover_providers()
        except Exception:
            providers = {}

        with ui.grid(columns=2).classes("w-full gap-4"):
            for p_name, data in providers.items():
                status_color = "text-green-400 border-green-500/30 bg-green-950/30" if data["available"] else "text-gray-400 border-gray-800 bg-gray-900/40"
                with ui.column().classes(f"p-4 rounded-xl border gap-2 shadow-lg {status_color}"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(p_name.upper()).classes("font-bold text-sm text-white")
                        status_badge = "AVAILABLE" if data["available"] else ("NOT CONFIGURED" if not data["configured"] else "UNREACHABLE")
                        ui.label(status_badge).classes("text-[10px] font-mono px-2 py-0.5 rounded bg-black/40")

                    if data["models"]:
                        ui.label(f"Available Models ({len(data['models'])}):").classes("text-xs font-semibold text-indigo-300 mt-1")
                        for m in data["models"]:
                            with ui.row().classes("w-full items-center justify-between bg-black/20 p-2 rounded text-xs"):
                                ui.label(m["name"]).classes("font-mono text-gray-200")
                                ui.label(f"Ctx: {m.get('context_length', 'N/A')}").classes("text-[10px] text-gray-400")
                    else:
                        reason = data.get("unavailable_reason", "Provider not detected")
                        ui.label(reason).classes("text-xs text-gray-400 italic")


def render_settings_view():
    """Render runtime settings and strategy preferences."""
    with ui.column().classes("w-full h-full p-4 gap-4 overflow-y-auto max-w-3xl"):
        with ui.row().classes("w-full items-center justify-between border-b border-gray-800 pb-2"):
            ui.label("System Settings & Runtime Configuration").classes("text-lg font-bold text-indigo-300")

        with ui.column().classes("w-full bg-gray-900/80 p-4 rounded-xl border border-gray-800 gap-3 text-xs"):
            ui.label("Search Engine Configuration").classes("font-bold text-sm text-indigo-200")
            ui.markdown("KhabriChacha uses **SearxNG** (`https://searx.be`) alongside **DuckDuckGo** fallback.").classes("text-gray-300")
            
            ui.label("Dual-LLM Engine Architecture").classes("font-bold text-sm text-indigo-200 mt-2")
            ui.markdown("- **LLM-1 (Router):** Fast router model (`qwen2.5:0.5b` or `gemini-2.0-flash`) handles query classification and adaptive planning.\n- **LLM-2 (Analysis):** High-capacity reasoning model (`qwen2.5:3b` or `gemini-2.0-pro`) synthesizes final evidence.").classes("text-gray-300")


def render_logs_view():
    """Render full-height system execution log viewer."""
    with ui.column().classes("w-full h-full p-4 gap-2 overflow-hidden"):
        ui.label("System Execution & Event Bus Logs").classes("text-lg font-bold text-indigo-300 flex-shrink-0")
        import khabrichacha.ui.ui_state as ui_state
        ui_state.log_view = ui.log().classes("w-full log-view flex-1")

