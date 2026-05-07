from __future__ import annotations
from typing import Callable, Optional, Dict, Tuple
import traceback
import msgpack

from ..utils.log import _logger
from ..nodes.loop_manager import TaskLoopManager
from ..utils.msg import RequestT, ResponseT, ResponseStatus
from ..transports.tcp_server import TcpServerManager

HandlerFunc = Callable[[RequestT], ResponseT]
ServiceCallback = Callable[[bytes], bytes]


class ServiceManager:
    """Manages services by registering handlers with TcpServerManager."""

    def __init__(
        self,
        tcp_server: TcpServerManager,
        loop_manager: TaskLoopManager,
    ) -> None:
        """Initialize the ServiceManager.

        Args:
            tcp_server: The shared TcpServerManager that dispatches
                        SERVICE_REQUEST frames to registered handlers.
            loop_manager: TaskLoopManager for running handlers in executor.
        """
        self._tcp_server = tcp_server
        self.loop_manager = loop_manager
        self._running: bool = True

    @property
    def port(self) -> int:
        return self._tcp_server.port

    @staticmethod
    def _wrap_handler(handler: HandlerFunc) -> ServiceCallback:
        """Static helper to wrap a standard handler with msgpack logic."""

        def wrapper(request_bytes: bytes) -> bytes:
            try:
                arg = msgpack.unpackb(request_bytes, raw=False)
                result = msgpack.packb(handler(arg), use_bin_type=True)
                assert result is not None, "msgpack.packb returned None"
                return result
            except msgpack.ExtraData as e:
                _logger.error("Message unpacking error: %s", e)
                return b""

        return wrapper

    def register_service(self, service_name: str, handler: HandlerFunc) -> None:
        """Register a service with a given name and handler function."""
        wrapped = self._wrap_handler(handler)
        self._tcp_server.register_service(service_name, wrapped)
        _logger.debug("Service '%s' registered successfully.", service_name)

    def stop(self) -> None:
        """Stop the service manager."""
        self._running = False
        _logger.debug("ServiceManager has been stopped")
