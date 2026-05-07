import msgpack
import pytest

from pyzlc.sockets.service_manager import ServiceManager


@pytest.mark.unit
def test_wrap_handler_unpacks_request_and_packs_response():
    wrapped = ServiceManager._wrap_handler(
        lambda request: {"sum": request["a"] + request["b"]}
    )

    response = wrapped(msgpack.packb({"a": 2, "b": 5}, use_bin_type=True))

    assert msgpack.unpackb(response, raw=False) == {"sum": 7}


@pytest.mark.unit
def test_wrap_handler_returns_empty_bytes_for_invalid_msgpack():
    wrapped = ServiceManager._wrap_handler(lambda request: request)
    valid_message_with_trailing_bytes = msgpack.packb({"ok": True}) + b"trailing"

    assert wrapped(valid_message_with_trailing_bytes) == b""
