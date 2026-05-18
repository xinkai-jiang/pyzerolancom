from __future__ import annotations
import os
import time
import traceback
from asyncio import sleep as async_sleep
from typing import Callable, Optional

import zmq
import msgpack

from ..nodes.zmq_socket_manager import ZMQSocketManager
from ..utils.log import _logger
from ..nodes.lancom_node import LanComNode
from ..utils.msg import MessageT, get_socket_addr


class Publisher:
    """Publishes messages to a topic."""

    def __init__(self, topic_name: str, group_name: Optional[str] = None, buffer_size: int = 1000):
        self.name = topic_name
        node = LanComNode.get_instance(group_name)
        self.loop_manager = node.loop_manager
        nodes_info_manager = node.nodes_info_manager
        local_node_info = nodes_info_manager.local_node_info
        self._socket = ZMQSocketManager.get_instance().create_socket(zmq.PUB)
        self._socket.setsockopt(zmq.SNDHWM, buffer_size)
        self._socket.bind(f"tcp://{local_node_info['ip']}:0")
        self.url, self.port = get_socket_addr(self._socket)
        ipc_dir = f"/tmp/zlc/{node.group_name}/{topic_name}"
        os.makedirs(ipc_dir, exist_ok=True)
        self._socket.bind(f"ipc://{ipc_dir}/topic.sock")
        os.chmod(f"{ipc_dir}/topic.sock", 0o666)
        nodes_info_manager.register_local_publisher(self.name, self.port)

    def publish(self, msg: MessageT, copy: bool = True) -> None:
        """Publish a message in bytes."""
        msgpacked = msgpack.packb(msg)
        self._socket.send(msgpacked, copy=copy)

    def on_shutdown(self) -> None:
        """Shutdown the publisher socket."""
        self._socket.close()


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
