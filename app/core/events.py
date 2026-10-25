"""
Simple in-process event bus for domain events.

Enables loose coupling between domains.
Events are published synchronously to registered handlers.
For async side effects (notifications, projections), handlers
should enqueue Celery tasks rather than doing the work inline.
"""

import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Dict[str, Any]], None]


class EventBus:
    """
    Synchronous in-process event bus.

    Handlers are called in registration order.
    Exceptions in one handler do not prevent other handlers from running.
    """

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
        logger.debug(f"Handler registered for event '{event_name}'")

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Remove a handler for a specific event type."""
        if event_name in self._handlers:
            self._handlers[event_name].remove(handler)
            if not self._handlers[event_name]:
                del self._handlers[event_name]

    async def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        """
        Publish an event to all registered handlers.

        Handlers are called sequentially. Exceptions are logged
        but do not prevent other handlers from executing.
        """
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            logger.debug(f"No handlers registered for event '{event_name}'")
            return

        logger.info(
            f"Publishing event '{event_name}'",
            extra={"event_name": event_name, "payload_keys": list(payload.keys())},
        )

        for handler in handlers:
            try:
                await handler(payload) if hasattr(handler, '__await__') else handler(payload)
            except Exception as e:
                logger.error(
                    f"Handler failed for event '{event_name}': {e}",
                    exc_info=True,
                    extra={"event_name": event_name, "handler": handler.__name__},
                )


# Global event bus instance
event_bus = EventBus()