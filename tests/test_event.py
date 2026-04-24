import pytest

from pyzlc.utils.event import Event


@pytest.mark.unit
def test_event_subscribe_emit_and_unsubscribe():
    event = Event[str]()
    received = []

    def handler(value: str) -> None:
        received.append(value)

    event.subscribe(handler)
    event("first")
    event.unsubscribe(handler)
    event("second")

    assert received == ["first"]
    assert len(event) == 0
    assert bool(event) is False


@pytest.mark.unit
def test_event_does_not_subscribe_handler_twice():
    event = Event[int]()

    def handler(value: int) -> None:
        pass

    event.subscribe(handler)
    event.subscribe(handler)

    assert len(event) == 1


@pytest.mark.unit
def test_event_clear_removes_handlers():
    event = Event[str]()
    event.subscribe(lambda value: None)

    event.clear()

    assert len(event) == 0
