import asyncio

import msgpack
import pytest

from pyzlc.sockets.service_manager import ServiceManager
from pyzlc.utils.msg import ResponseStatus


@pytest.mark.unit
def test_wrap_handler_unpacks_request_and_packs_response():
    wrapped = ServiceManager._wrap_handler(lambda request: {"sum": request["a"] + request["b"]})

    response = wrapped(msgpack.packb({"a": 2, "b": 5}, use_bin_type=True))

    assert msgpack.unpackb(response, raw=False) == {"sum": 7}


@pytest.mark.unit
def test_wrap_handler_returns_empty_bytes_for_invalid_msgpack():
    wrapped = ServiceManager._wrap_handler(lambda request: request)
    valid_message_with_trailing_bytes = msgpack.packb({"ok": True}) + b"trailing"

    assert wrapped(valid_message_with_trailing_bytes) == b""


@pytest.mark.unit
def test_handle_request_returns_no_service_without_socket():
    manager = ServiceManager.__new__(ServiceManager)
    manager._running = True

    status, payload = asyncio.run(
        manager._handle_request("missing", b"", services={})
    )

    assert status == ResponseStatus.NOSERVICE.encode()
    assert payload == b""


@pytest.mark.unit
def test_handle_request_runs_registered_service():
    class FakeLoopManager:
        async def run_in_executor(self, func, *args):
            return func(*args)

    manager = ServiceManager.__new__(ServiceManager)
    manager._running = True
    manager.loop_manager = FakeLoopManager()

    status, payload = asyncio.run(
        manager._handle_request(
            "echo",
            b"payload",
            services={"echo": lambda request: request.upper()},
        )
    )

    assert status == ResponseStatus.SUCCESS.encode()
    assert payload == b"PAYLOAD"
