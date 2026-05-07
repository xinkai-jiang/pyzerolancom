from __future__ import annotations
import os
from typing import Callable, Optional

import msgpack

from ..utils.log import _logger
from ..nodes.lancom_node import LanComNode
from ..utils.msg import MessageT
from ..transports.ipc_server import IpcServer
from ..transports.tcp_server import TcpServerManager


class Publisher:
    """Publishes messages to a topic."""

    def __init__(self, topic_name: str, group_name: Optional[str] = None, buffer_size: int = 1000):
        self.name = topic_name
        node = LanComNode.get_instance(group_name)
        self.loop_manager = node.loop_manager
        nodes_info_manager = node.nodes_info_manager
        self._tcp_server: TcpServerManager = node.tcp_server

        # IPC server for same-host optimization
        ipc_dir = f"/tmp/zlc/{node.group_name}/{topic_name}"
        os.makedirs(ipc_dir, exist_ok=True)
        self._ipc_server = IpcServer(f"{ipc_dir}/topic.sock")
        self.loop_manager.submit_loop_task(self._ipc_server.start())

        # Use the shared TCP server's port (all topics share one port)
        self.url = f"tcp://{node.node_ip}:{self._tcp_server.port}"
        self.port = self._tcp_server.port
        nodes_info_manager.register_local_publisher(self.name, self.port)

    def publish(self, msg: MessageT) -> None:
        """Publish a message. Schedules fan-out to TCP and IPC clients."""
        msgpacked: bytes = msgpack.packb(msg, use_bin_type=True)  # type: ignore[assignment]
        # Schedule both TCP and IPC fan-out on the event loop
        self.loop_manager.submit_loop_task(
            self._publish_async(msgpacked)
        )

    async def _publish_async(self, data: bytes) -> None:
        """Fan out to TCP subscribers and IPC subscribers."""
        await self._tcp_server.publish_topic(self.name, data)
        await self._ipc_server.publish(self.name, data)

    def on_shutdown(self) -> None:
        """Shutdown the publisher."""
        self._ipc_server.close()


class Streamer(Publisher):
    """Streams messages to a topic at a fixed rate."""

    def __init__(
        self,
        topic_name: str,
        update_func: Callable[[], MessageT],
        fps: int,
        start_streaming: bool = False,
        group_name: Optional[str] = None,
        buffer_size: int = 1000,
    ):
        super().__init__(topic_name, group_name, buffer_size)
        self.running = False
        self.dt: float = 1 / fps
        self.update_func = update_func
        if start_streaming:
            self.start_streaming()

    def start_streaming(self):
        """Start the streaming loop."""
        self.loop_manager.submit_loop_task(self.update_loop())

    async def update_loop(self) -> None:
        """Streams messages at the specified rate."""
        self.running = True
        import time
        import traceback
        from asyncio import sleep as async_sleep

        last = 0.0
        _logger.info("Topic %s starts streaming", self.name)
        while self.running:
            try:
                diff = time.monotonic() - last
                if diff < self.dt:
                    await async_sleep(self.dt - diff)
                last = time.monotonic()
                self.publish(self.update_func())
            except Exception as e:
                _logger.error("Error when streaming %s: %s", self.name, e)
                traceback.print_exc()
                raise e
        _logger.info("Streamer for topic %s is stopped", self.name)
