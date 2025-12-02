from __future__ import annotations
from typing import Callable, Any, overload
import traceback
import asyncio
import zmq.asyncio
import msgpack

from ..utils.lancom_type import AsyncSocket
from ..utils.log import logger
from .loop_manager import LanComLoopManager
from ..utils.msg import get_socket_addr

class ServiceManager:
    """Manages services using a REP socket."""

    def __init__(self, url: str) -> None:
        """Initialize the ServiceManager with a REP socket."""
        self.services: dict[str, dict] = {}
        self.res_socket: AsyncSocket = zmq.asyncio.Context().socket(zmq.REP)
        self.callable_services: dict[str, Callable[[bytes], bytes]] = {}
        self.res_socket.bind(url)
        url, self.port = get_socket_addr(self.res_socket)
        logger.info("ServiceManager REP socket bound to %s", url)
        self._running: bool = True
        self.loop_manager = LanComLoopManager.get_instance()
        self.loop_manager.submit_loop_task(
            self.service_loop(self.res_socket, self.callable_services)
        )

    def register_service(self, service_name: str, handler: Callable[[Any], Any]) -> None:
        """Register a service with a handler function."""
        self.callable_services[service_name] = handler


    async def service_loop(
        self,
        service_socket: zmq.asyncio.Socket,
        services: dict[str, Callable[[Any], Any]],
    ) -> None:
        """Asynchronously handles incoming service requests."""
        while self._running:
            try:
                name_bytes, request = await service_socket.recv_multipart()
            except Exception as e:
                logger.error("Error occurred when receiving request: %s", e)
                traceback.print_exc()
            service_name = name_bytes.decode()
            if service_name not in services.keys():
                logger.error("Service %s is not available", service_name)
                continue
            try:
                result = None
                if request == b"":
                    result = await asyncio.wait_for(
                        self.loop_manager.run_in_executor(
                            services[service_name]
                        ),
                        timeout=2.0,
                    )
                else:
                    unpacked = msgpack.unpackb(request, strict_map_key=False, raw=False)
                    result = await asyncio.wait_for(
                        self.loop_manager.run_in_executor(
                            services[service_name], unpacked
                        ),
                        timeout=2.0,
                    )
                packed_result = msgpack.packb(result, use_bin_type=True)
                await service_socket.send(packed_result)
            except asyncio.TimeoutError:
                logger.error("Timeout: callback function took too long")
                await service_socket.send_string("TIMEOUT")
            except msgpack.ExtraData as e:
                logger.error("Message unpacking error: %s", e)
                await service_socket.send_string("UNPACKING_ERROR")
            except Exception as e:
                logger.error(
                    "One error occurred when processing the Service "
                    "%s: %s", service_name, e
                )
                traceback.print_exc()
                await service_socket.send_string("ERROR")
        logger.info("Service loop has been stopped")
