"""Event/Observer pattern utility similar to C# Events."""

from __future__ import annotations
from typing import Callable, Generic, TypeVar, List


T = TypeVar("T")


class Event(Generic[T]):
    """A simple event class that implements the observer pattern.
    
    Similar to C# Events, this allows multiple handlers to subscribe
    to an event and be notified when the event is raised.
    
    Usage:
        # Create an event
        on_message_received: Event[str] = Event()
        
        # Subscribe to the event
        def handler(msg: str):
            print(f"Received: {msg}")
        
        on_message_received += handler
        # or: on_message_received.subscribe(handler)
        
        # Raise the event
        on_message_received.emit("Hello!")
        # or: on_message_received("Hello!")
        
        # Unsubscribe
        on_message_received -= handler
        # or: on_message_received.unsubscribe(handler)
    
    Type Parameters:
        T: The type of the argument passed to handlers (use None for no args)
    """

    def __init__(self) -> None:
        self._handlers: List[Callable[[T], None]] = []

    def emit(self, arg: T) -> None:
        """Emit the event, notifying all subscribed handlers.
        
        Args:
            arg: The argument to pass to all handlers.
        """
        for handler in self._handlers[:]:  # Copy list to allow modification during iteration
            handler(arg)

    def clear(self) -> None:
        """Remove all subscribed handlers."""
        self._handlers.clear()

    def subscribe(self, handler: Callable[[T], None]) -> None:
        """Subscribe a handler to the event."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unsubscribe(self, handler: Callable[[T], None]) -> None:
        """Unsubscribe a handler from the event."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def __call__(self, arg: T) -> None:
        """Allow calling the event directly to emit."""
        self.emit(arg)

    def __len__(self) -> int:
        """Return the number of subscribed handlers."""
        return len(self._handlers)

    def __bool__(self) -> bool:
        """Return True if there are any subscribed handlers."""
        return len(self._handlers) > 0

