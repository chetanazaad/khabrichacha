"""
KhabriChacha
Application Entry Point

Responsibilities:
- Load configuration
- Initialize logging
- Launch UI

DO NOT place any business logic here.
"""

from nicegui import ui
from khabrichacha.ui.main import start_application

if __name__ in {"__main__", "__mp_main__"}:
    start_application()
    ui.run(
        title="KhabriChacha",
        host="127.0.0.1",
        port=8080,
        reload=False,
        dark=True,
    )
