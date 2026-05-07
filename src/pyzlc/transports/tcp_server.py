"""Single-port asyncio TCP server for pyzlc transport.

TcpServerManager runs a single asyncio TCP server per node. It handles:
  - Topic fan-out: maintains a topic→set(writers) registry and fans out
    TOPIC_PUBLISH messages to all subscribed clients.
  - Service dispatch: dispatches SERVICE_REQUEST frames to registered
    service handlers and sends back SERVICE_RESPONSE on the same connection.
  - Subscription management: handles TOPIC_SUBSCRIBE / TOPIC_UNSUBSCRIBE frames.
"""

from __future__ import annotations
import asyncio
import traceback
from typing import Callable, Dict, Optional, Set, Tuple

from .protocol import (
    TOPIC_PUBLISH,
    SERVICE_REQUEST,
    SERVICE_RESPONSE,
    TOPIC_SUBSCRIBE,
    TOPIC_UNSUBSCRIBE,
    decode_service_request,
    decode_topic_subscribe,
    encode_frame,
    encode_service_request,
    encode_topic_publish,
    read_frame,
    write_frame,
)
from ..utils.log import _logger


ServiceHandler = Callable[[bytes], bytes]


class TcpServerManager:
    """Manages a single TCP server that multiplexes pub/sub and services."""

    def __init__(self, host: str) -> None:
        self._host = host
        self._server: Optional[asyncio.AbstractServer] = None
        self._port: int = 0

        # Topic fan-out: topic_name → set of connected writers
        self._topic_subscribers: Dict[str, Set[asyncio.StreamWriter]] = {}

        # Service handlers: service_name → handler(bytes) → bytes
        self._service_handlers: Dict[str, ServiceHandler] = {}

        # Active client tasks for cleanup
        self._client_tasks: Set[asyncio.Task] = set()

    @property
    def port(self) -> int:
        return self._port

    async def start(self) -> None:
        """Start the TCP server on an ephemeral port."""
        self._server = await asyncio.start_server(
            self._handle_client, self._host, 0
        )
        # Retrieve the bound port
        sock = self._server.sockets[0]
        self._port = sock.getsockname()[1]
        _logger.info(
            "TcpServerManager listening on tcp://%s:%d", self._host, self._port
        )

    async def stop(self) -> None:
        """Stop the server and close all client connections (async)."""
        self.close()
        # Await server close completion if still possible
        if self._server is not None:
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None

    def close(self) -> None:
        """Synchronously close the server. Safe to call during shutdown."""
        if self._server is not None:
            self._server.close()
        # Cancel all client handler tasks
        for task in self._client_tasks:
            task.cancel()
        self._client_tasks.clear()
        self._topic_subscribers.clear()
        _logger.debug("TcpServerManager stopped")

    # --- Pub/Sub ---

    async def publish_topic(self, topic_name: str, data: bytes) -> None:
        """Fan out a topic message to all subscribed TCP clients."""
        writers = self._topic_subscribers.get(topic_name, set())
        if not writers:
            return
        payload = encode_topic_publish(topic_name, data)
        frame = encode_frame(TOPIC_PUBLISH, payload)
        # Fan out in parallel
        dead_writers: list = []
        for writer in writers:
            try:
                writer.write(frame)
            except (ConnectionError, RuntimeError):
                dead_writers.append(writer)
        # Clean up dead writers
        for w in dead_writers:
            writers.discard(w)
        # Drain all writers
        if writers:
            await asyncio.gather(
                *(writer.drain() for writer in writers),
                return_exceptions=True,
            )

    # --- Services ---

    def register_service(self, service_name: str, handler: ServiceHandler) -> None:
        """Register a service handler."""
        self._service_handlers[service_name] = handler

    def unregister_service(self, service_name: str) -> None:
        """Unregister a service handler."""
        self._service_handlers.pop(service_name, None)

    # --- Client handling ---

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming client connection."""
        task = asyncio.current_task()
        if task is not None:
            self._client_tasks.add(task)
        try:
            while True:
                result = await read_frame(reader)
                if result is None:
                    break  # Connection closed
                msg_type, payload = result
                if msg_type == TOPIC_SUBSCRIBE:
                    topic = decode_topic_subscribe(payload)
                    self._add_subscriber(topic, writer)
                elif msg_type == TOPIC_UNSUBSCRIBE:
                    topic = decode_topic_subscribe(payload)
                    self._remove_subscriber(topic, writer)
                elif msg_type == SERVICE_REQUEST:
                    await self._handle_service_request(writer, payload)
                else:
                    _logger.warning(
                        "Unknown message type 0x%02x from %s", msg_type,
                        writer.get_extra_info("peername")
                    )
        except asyncio.CancelledError:
            pass
        except Exception:
            _logger.error("Client handler error: %s", traceback.format_exc())
        finally:
            self._remove_writer_from_all_topics(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            if task is not None:
                self._client_tasks.discard(task)

    def _add_subscriber(
        self, topic_name: str, writer: asyncio.StreamWriter
    ) -> None:
        if topic_name not in self._topic_subscribers:
            self._topic_subscribers[topic_name] = set()
        self._topic_subscribers[topic_name].add(writer)
        _logger.debug("Client subscribed to topic '%s'", topic_name)

    def _remove_subscriber(
        self, topic_name: str, writer: asyncio.StreamWriter
    ) -> None:
        subs = self._topic_subscribers.get(topic_name)
        if subs:
            subs.discard(writer)
            if not subs:
                del self._topic_subscribers[topic_name]

    def _remove_writer_from_all_topics(
        self, writer: asyncio.StreamWriter
    ) -> None:
        for subs in list(self._topic_subscribers.values()):
            subs.discard(writer)

    async def _handle_service_request(
        self, writer: asyncio.StreamWriter, payload: bytes
    ) -> None:
        """Dispatch a service request and send back the response."""
        service_name, request_bytes = decode_service_request(payload)
        handler = self._service_handlers.get(service_name)
        if handler is None:
            status = b"NOSERVICE"
            result = b""
        else:
            try:
                result = handler(request_bytes)
                status = b"SUCCESS"
            except Exception as e:
                _logger.error(
                    "Service '%s' handler error: %s", service_name, e
                )
                status = b"SERVICE_FAIL"
                result = b""
        response_payload = status + result
        try:
            await write_frame(writer, SERVICE_RESPONSE, response_payload)
        except (ConnectionError, RuntimeError) as e:
            _logger.error(
                "Failed to send service response for '%s': %s",
                service_name, e,
            )
