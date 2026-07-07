"""
Event Bus

Provides a publish-subscribe mechanism for broadcasting research events
to decoupled listeners (e.g., UI callbacks, loggers, WebSocket streams).
"""

from typing import Callable, Dict, List
from deployment.runtime.models.research_event import ResearchEvent
from loguru import logger

EventCallback = Callable[[ResearchEvent], None]

class EventBus:
    """Simple pub/sub event bus for the research runtime."""

    def __init__(self):
        self._listeners: Dict[str, List[EventCallback]] = {}
        # '*' represents a catch-all for all events
        self._listeners['*'] = []

    def subscribe(self, event_level: str, callback: EventCallback) -> None:
        """
        Subscribe to events of a specific level (e.g., 'INFO', 'ERROR').
        Use '*' to subscribe to all events.
        """
        level = event_level.upper()
        if level not in self._listeners:
            self._listeners[level] = []
        if callback not in self._listeners[level]:
            self._listeners[level].append(callback)

    def unsubscribe(self, event_level: str, callback: EventCallback) -> None:
        """Remove a subscription."""
        level = event_level.upper()
        if level in self._listeners and callback in self._listeners[level]:
            self._listeners[level].remove(callback)

    def publish(self, event: ResearchEvent) -> None:
        """Publish an event to all relevant listeners."""
        level = event.level.upper()
        
        # Determine which callbacks to trigger
        callbacks = set(self._listeners.get('*', []))
        if level in self._listeners:
            callbacks.update(self._listeners[level])
            
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                # Catch callback exceptions so they don't break the main loop
                logger.error(f"EventBus callback error: {e}")

    # Convenience methods for quick publishing
    def info(self, component: str, message: str, **metadata) -> None:
        self.publish(ResearchEvent(level="INFO", component=component, message=message, metadata=metadata))
        
    def warn(self, component: str, message: str, **metadata) -> None:
        self.publish(ResearchEvent(level="WARNING", component=component, message=message, metadata=metadata))
        
    def error(self, component: str, message: str, **metadata) -> None:
        self.publish(ResearchEvent(level="ERROR", component=component, message=message, metadata=metadata))
        
    def debug(self, component: str, message: str, **metadata) -> None:
        self.publish(ResearchEvent(level="DEBUG", component=component, message=message, metadata=metadata))

    # ── Standard Pipeline Events ──────────────────────────────
    def research_started(self, message: str = "Research started.", **kwargs) -> None:
        self.info("Controller", message, event_type="ResearchStarted", **kwargs)

    def classifier_completed(self, message: str = "Classification completed.", **kwargs) -> None:
        self.info("QueryClassifier", message, event_type="ClassifierCompleted", **kwargs)

    def retrieval_started(self, message: str = "Retrieval started.", **kwargs) -> None:
        self.info("Retriever", message, event_type="RetrievalStarted", **kwargs)

    def retrieval_completed(self, message: str = "Retrieval completed.", **kwargs) -> None:
        self.info("Retriever", message, event_type="RetrievalCompleted", **kwargs)

    def search_started(self, message: str = "Search started.", **kwargs) -> None:
        self.info("SearchTool", message, event_type="SearchStarted", **kwargs)

    def search_completed(self, message: str = "Search completed.", **kwargs) -> None:
        self.info("SearchTool", message, event_type="SearchCompleted", **kwargs)

    def fetch_started(self, message: str = "Fetch started.", **kwargs) -> None:
        self.info("FetchTool", message, event_type="FetchStarted", **kwargs)

    def fetch_completed(self, message: str = "Fetch completed.", **kwargs) -> None:
        self.info("FetchTool", message, event_type="FetchCompleted", **kwargs)

    def llm_started(self, message: str = "LLM generation started.", **kwargs) -> None:
        self.info("LLM", message, event_type="LLMStarted", **kwargs)

    def llm_completed(self, message: str = "LLM generation completed.", **kwargs) -> None:
        self.info("LLM", message, event_type="LLMCompleted", **kwargs)

    def formatting_started(self, message: str = "Formatting started.", **kwargs) -> None:
        self.info("Formatter", message, event_type="FormattingStarted", **kwargs)

    def formatting_completed(self, message: str = "Formatting completed.", **kwargs) -> None:
        self.info("Formatter", message, event_type="FormattingCompleted", **kwargs)

    def project_created(self, message: str = "Project created.", **kwargs) -> None:
        self.info("ProjectManager", message, event_type="ProjectCreated", **kwargs)

    def project_saved(self, message: str = "Project saved.", **kwargs) -> None:
        self.info("ProjectManager", message, event_type="ProjectSaved", **kwargs)

    def report_generated(self, message: str = "Report generated.", **kwargs) -> None:
        self.info("ReportExporter", message, event_type="ReportGenerated", **kwargs)

    def execution_finished(self, message: str = "Execution finished.", **kwargs) -> None:
        self.info("Controller", message, event_type="ExecutionFinished", **kwargs)

    def execution_failed(self, message: str = "Execution failed.", **kwargs) -> None:
        self.error("Controller", message, event_type="ExecutionFailed", **kwargs)
