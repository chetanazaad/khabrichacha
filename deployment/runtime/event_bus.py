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
