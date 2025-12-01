from __future__ import annotations
from typing import Callable
import traceback
import asyncio
import zmq.asyncio

from ..utils.lancom_type import AsyncSocket
from ..utils.log import logger
from .loop_manager import LanComLoopManager

class ServiceManager:
    """Manages services using a REP socket."""

    def __init__(self, url: str) -> None:
        """Initialize the ServiceManager with a REP socket."""
        self.services: dict[str, dict] = {}
        self.res_socket: AsyncSocket = zmq.asyncio.Context().socket(zmq.REP)
        self.callable_services: dict[str, Callable[[bytes], bytes]] = {}
        self.res_socket.bind(url)
        self._running: bool = True
        self.loop_manager = LanComLoopManager.get_instance()

    def register_service(self, service_name: str, handler: Callable[[bytes], bytes]) -> None:
        """Register a service with a handler function."""
        self.callable_services[service_name] = handler

    async def service_loop(
        self,
        service_socket: zmq.asyncio.Socket,
        services: dict[str, Callable[[bytes], bytes]],
    ) -> None:
        """Asynchronously handles incoming service requests."""
        while self._running:
            try:
                name_bytes, request = await service_socket.recv_multipart()
            except Exception as e:
                logger.error(f"Error occurred when receiving request: {e}")
                traceback.print_exc()
            service_name = name_bytes.decode()
            if service_name not in services.keys():
                logger.error(f"Service {service_name} is not available")
                continue
            try:
                result = await asyncio.wait_for(
                    self.loop_manager.run_in_executor(
                        services[service_name], request
                    ),
                    timeout=2.0,
                )
                # result = services[service_name](request)
                # logger.debug(service_name, result)
                await service_socket.send(result)
            except asyncio.TimeoutError:
                logger.error("Timeout: callback function took too long")
                await service_socket.send_string("TIMEOUT")
            except Exception as e:
                logger.error(
                    f"One error occurred when processing the Service "
                    f'"{service_name}": {e}'
                )
                traceback.print_exc()
                await service_socket.send_string("ERROR")
        logger.info("Service loop has been stopped")