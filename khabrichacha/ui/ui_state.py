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
strategy_select: Optional[ui.select] = None
sources_input: Optional[ui.number] = None

# Strategy indicators
strategy_indicator: Optional[ui.label] = None
confidence_indicator: Optional[ui.label] = None
latency_indicator: Optional[ui.label] = None
cost_indicator: Optional[ui.label] = None
planner_indicator: Optional[ui.label] = None
search_indicator: Optional[ui.label] = None
reasoning_indicator: Optional[ui.label] = None
evidence_indicator: Optional[ui.label] = None
report_indicator: Optional[ui.label] = None
project_indicator: Optional[ui.label] = None

# Retrieval indicators
sources_found_indicator: Optional[ui.label] = None
sources_selected_indicator: Optional[ui.label] = None
duplicates_removed_indicator: Optional[ui.label] = None
trust_score_indicator: Optional[ui.label] = None
output_format_indicator: Optional[ui.label] = None
knowledge_cache_indicator: Optional[ui.label] = None
consensus_score_indicator: Optional[ui.label] = None

# Async event loop of the main thread
main_loop: Optional[Any] = None

# Save project button state
save_project_btn: Optional[ui.button] = None
current_project_id: Optional[str] = None
downloads_container: Optional[ui.column] = None
