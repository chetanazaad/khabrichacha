"""
Main UI entry point for the NiceGUI application.
Binds brand palette, loads custom CSS, and builds the layout grid.
The server is started from app.py to satisfy NiceGUI's main-module check.
"""

from nicegui import ui, app
from khabrichacha.ui.theme import get_custom_css
from khabrichacha.ui.components import build_layout

@ui.page('/')
def index_page():
    ui.add_head_html(get_custom_css())
    build_layout()

def start_application():
    @app.on_startup
    def startup():
        import asyncio
        import khabrichacha.ui.ui_state as ui_state
        from loguru import logger
        
        # Capture the running event loop of the main thread
        ui_state.main_loop = asyncio.get_running_loop()
        
        # Configure custom loguru sink to update the NiceGUI log component
        def safe_push(text):
            try:
                if ui_state.log_view:
                    ui_state.log_view.push(text)
            except RuntimeError as e:
                if "deleted" in str(e):
                    ui_state.log_view = None
            except Exception:
                pass

        def ui_log_sink(message):
            if ui_state.log_view:
                try:
                    ui_state.main_loop.call_soon_threadsafe(safe_push, message.rstrip())
                except Exception:
                    pass
        
        logger.add(ui_log_sink, format="{time:HH:mm:ss} | {level:7} | {message}")
