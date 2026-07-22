from nicegui import ui


def render_page(page_name: str) -> None:
    if page_name == "projects":
        with ui.column().classes("w-full gap-3"):
            ui.markdown("## Projects")
            ui.markdown("Saved projects and recent research sessions appear here.")
    elif page_name == "models":
        with ui.column().classes("w-full gap-3"):
            ui.markdown("## Models")
            ui.markdown("Model availability and provider status are shown here.")
    elif page_name == "settings":
        with ui.column().classes("w-full gap-3"):
            ui.markdown("## Settings")
            ui.markdown("Configuration and runtime preferences will be managed here.")
    elif page_name == "logs":
        with ui.column().classes("w-full gap-3"):
            ui.markdown("## Logs")
            ui.markdown("Recent execution logs appear here.")
    elif page_name == "about":
        with ui.column().classes("w-full gap-3"):
            ui.markdown("## About")
            ui.markdown("KhabriChacha is a research assistant with local-first and cloud-ready execution paths.")
    else:
        with ui.column().classes("w-full gap-3"):
            ui.markdown("## Research")
            ui.markdown("Use the main workspace to run new research missions.")
