"""
Main UI entry point for the NiceGUI application.
Binds brand palette, loads custom CSS, and builds the layout grid.
The server is started from app.py to satisfy NiceGUI's main-module check.
"""

from nicegui import ui
from khabrichacha.ui.theme import get_custom_css
from khabrichacha.ui.components import build_layout

@ui.page('/')
def index_page():
    ui.add_head_html(get_custom_css())
    build_layout()

def start_application():
    pass
