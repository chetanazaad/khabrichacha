from typing import Optional, Any
from nicegui import ui

# NiceGUI UI component references
results_markdown: Optional[ui.markdown] = None
references_markdown: Optional[ui.markdown] = None
progress_bar: Optional[ui.linear_progress] = None
progress_label: Optional[ui.label] = None
status_label: Optional[ui.label] = None
log_view: Optional[ui.log] = None
model_label: Optional[ui.label] = None
project_label: Optional[ui.label] = None

# UI Input components
goal_input: Optional[ui.textarea] = None
model_select: Optional[ui.select] = None
depth_select: Optional[ui.select] = None
sources_input: Optional[ui.number] = None

# Async event loop of the main thread
main_loop: Optional[Any] = None
