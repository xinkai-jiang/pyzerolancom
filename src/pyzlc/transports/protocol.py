"""Binary wire protocol for asyncio-based pyzlc transport.

Message framing:
    [1 byte: msg_type] [4 bytes: payload_length (big-endian)] [variable: payload]

Message types:
    0x01 - TOPIC_PUBLISH:      payload = [topic_name_len:2][topic_name][msgpack_data]
    0x02 - SERVICE_REQUEST:    payload = [service_name_len:2][service_name][request_bytes]
    0x03 - SERVICE_RESPONSE:   payload = [status_byte][result_bytes]
    0x04 - TOPIC_SUBSCRIBE:    payload = [topic_name_len:2][topic_name]
    0x05 - TOPIC_UNSUBSCRIBE:  payload = [topic_name_len:2][topic_name]
"""

from __future__ import annotations
import struct
from typing import Optional, Tuple

# --- Message type constants ---
TOPIC_PUBLISH = 0x01
SERVICE_REQUEST = 0x02
SERVICE_RESPONSE = 0x03
TOPIC_SUBSCRIBE = 0x04
TOPIC_UNSUBSCRIBE = 0x05

# Frame format: 1 byte type + 4 bytes big-endian length
_FRAME_HEADER = struct.Struct("!BI")
_FRAME_HEADER_SIZE = 5


def encode_frame(msg_type: int, payload: bytes) -> bytes:
    """Encode a message frame with type and length-prefixed payload."""
    return _FRAME_HEADER.pack(msg_type, len(payload)) + payload


async def read_frame(reader) -> Optional[Tuple[int, bytes]]:
    """Read a single framed message from an asyncio StreamReader.

    Returns (msg_type, payload) or None if the connection is closed.
    """
    try:
        header = await reader.readexactly(_FRAME_HEADER_SIZE)
    except (asyncio.IncompleteReadError, ConnectionError):
        return None
    msg_type, payload_len = _FRAME_HEADER.unpack(header)
    try:
        payload = await reader.readexactly(payload_len)
    except (asyncio.IncompleteReadError, ConnectionError):
        return None
    return msg_type, payload


async def write_frame(writer, msg_type: int, payload: bytes) -> None:
    """Write a framed message to an asyncio StreamWriter."""
    writer.write(encode_frame(msg_type, payload))
    await writer.drain()


# --- Higher-level message helpers ---

_TOPIC_NAME_STRUCT = struct.Struct("!H")


def encode_topic_publish(topic_name: str, data: bytes) -> bytes:
    """Encode a TOPIC_PUBLISH payload."""
    topic_bytes = topic_name.encode("utf-8")
    return _TOPIC_NAME_STRUCT.pack(len(topic_bytes)) + topic_bytes + data


def decode_topic_publish(payload: bytes) -> Tuple[str, bytes]:
    """Decode a TOPIC_PUBLISH payload into (topic_name, data)."""
    name_len = _TOPIC_NAME_STRUCT.unpack(payload[:2])[0]
    topic_name = payload[2:2 + name_len].decode("utf-8")
    data = payload[2 + name_len:]
    return topic_name, data


def encode_topic_subscribe(topic_name: str) -> bytes:
    """Encode a TOPIC_SUBSCRIBE/TOPIC_UNSUBSCRIBE payload."""
    topic_bytes = topic_name.encode("utf-8")
    return _TOPIC_NAME_STRUCT.pack(len(topic_bytes)) + topic_bytes


def decode_topic_subscribe(payload: bytes) -> str:
    """Decode a TOPIC_SUBSCRIBE/TOPIC_UNSUBSCRIBE payload into topic_name."""
    name_len = _TOPIC_NAME_STRUCT.unpack(payload[:2])[0]
    return payload[2:2 + name_len].decode("utf-8")


def encode_service_request(service_name: str, request_bytes: bytes) -> bytes:
    """Encode a SERVICE_REQUEST payload."""
    name_bytes = service_name.encode("utf-8")
    return _TOPIC_NAME_STRUCT.pack(len(name_bytes)) + name_bytes + request_bytes


def decode_service_request(payload: bytes) -> Tuple[str, bytes]:
    """Decode a SERVICE_REQUEST payload into (service_name, request_bytes)."""
    name_len = _TOPIC_NAME_STRUCT.unpack(payload[:2])[0]
    service_name = payload[2:2 + name_len].decode("utf-8")
    request_bytes = payload[2 + name_len:]
    return service_name, request_bytes


import asyncio  # noqa: E402 (placed here to avoid circular import issues)
