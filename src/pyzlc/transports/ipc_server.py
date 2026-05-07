"""Unix domain socket server for same-host pub/sub optimization.

When a publisher and subscriber are on the same machine, they communicate
via a Unix domain socket at /tmp/zlc/<group>/<topic>/topic.sock instead of
going through the TCP stack. This provides lower latency and avoids TCP overhead.
"""

from __future__ import annotations
import asyncio
import os
import traceback
from typing import Set

from .protocol import (
    TOPIC_PUBLISH,
    encode_frame,
    encode_topic_publish,
    read_frame,
)
from ..utils.log import _logger


class IpcServer:
    """Per-topic Unix domain socket server for same-host pub/sub."""

    def __init__(self, socket_path: str) -> None:
        self._socket_path = socket_path
        self._server: asyncio.AbstractServer | None = None
        self._writers: Set[asyncio.StreamWriter] = set()
        self._client_tasks: Set[asyncio.Task] = set()

    @property
    def socket_path(self) -> str:
        return self._socket_path

    async def start(self) -> None:
        """Start the IPC server, cleaning up any stale socket file."""
        # Remove stale socket file if it exists
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass

        self._server = await asyncio.start_unix_server(
            self._handle_client, self._socket_path
        )
        _logger.debug("IpcServer listening on %s", self._socket_path)

    async def stop(self) -> None:
        """Stop the IPC server and clean up (async)."""
        self.close()
        if self._server is not None:
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None

    def close(self) -> None:
        """Synchronously close the IPC server. Safe to call during shutdown."""
        if self._server is not None:
            self._server.close()
        for task in self._client_tasks:
            task.cancel()
        self._client_tasks.clear()
        self._writers.clear()
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass

    async def publish(self, topic_name: str, data: bytes) -> None:
        """Publish a message to all connected IPC clients."""
        if not self._writers:
            return
        payload = encode_topic_publish(topic_name, data)
        frame = encode_frame(TOPIC_PUBLISH, payload)
        dead_writers: list = []
        for writer in self._writers:
            try:
                writer.write(frame)
            except (ConnectionError, RuntimeError):
                dead_writers.append(writer)
        for w in dead_writers:
            self._writers.discard(w)
        if self._writers:
            await asyncio.gather(
                *(writer.drain() for writer in self._writers),
                return_exceptions=True,
            )

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an IPC client — just keep connection alive and read frames."""
        task = asyncio.current_task()
        if task is not None:
            self._client_tasks.add(task)
        self._writers.add(writer)
        try:
            while True:
                result = await read_frame(reader)
                if result is None:
                    break  # Connection closed
                # IPC subscribers don't send messages; just consume to detect disconnection
        except asyncio.CancelledError:
            pass
        except Exception:
            _logger.error("IPC client error: %s", traceback.format_exc())
        finally:
            self._writers.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            if task is not None:
                self._client_tasks.discard(task)
