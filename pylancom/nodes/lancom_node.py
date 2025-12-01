from __future__ import annotations

import asyncio
import socket
import traceback
from typing import Optional

import msgpack
import zmq.asyncio

from ..utils.lancom_type import IPAddress, LanComMsg
from ..utils.log import logger
from ..utils.msg import create_heartbeat_message, create_hash_identifier
from .loop_manager import LanComLoopManager
from ..utils.lancom_type import NodeInfo
from .nodes_info_manager import NodesInfoManager

class LocalNodeInfo:
    
    def __init__(self, name: str, ip: IPAddress) -> None:
        self.name = name
        self.node_id = create_hash_identifier()
        self.ip = ip
        self._node_info: NodeInfo

    def create_heartbeat_message() -> bytes:
            return b"".join(
        [
            b"LANCOM",  # 6-byte header
            __VERSION_BYTES__,  # 3-byte version
            node_id.encode(),  # 36-byte NodeID
            port.to_bytes(2, "big"),  # 2-byte port
            info_id.to_bytes(4, "big"),  # 4-byte timestamp
        ]
    )
    
    def register_service(
        self,
        service_name: str
    ) -> None:
        pass
    
    def register_publisher(
        self,
        topic_name: str,
    ) -> None:
        pass


class LanComNodeBase:
    instance: Optional[LanComNodeBase] = None

    def __init__(
        self,
        node_name: str,
        node_ip: IPAddress,
        group: IPAddress = "224.0.0.1",
        group_port: int = 7720,
        interval: float = 1.0,
    ) -> None:
        super().__init__()
        self.node_ip = node_ip
        self.group = group
        self.group_port = group_port
        self.interval = interval
        self._local_info: LocalNodeInfo = LocalNodeInfo(
            node_name,
            create_hash_identifier(),
            node_ip,
        )
        self.zmq_context: zmq.asyncio.Context = zmq.asyncio.Context()
        self.nodes_manager: NodesInfoManager = NodesInfoManager()
        self.loop_manager: LanComLoopManager = LanComLoopManager()
        self._running: bool = False

    def create_socket(self, socket_type: int) -> zmq.asyncio.Socket:
        return self.zmq_context.socket(socket_type)

    async def multicast_loop(self):
        """Send heartbeat messages via ZeroMQ multicast (epgm)."""
        try:
            # epgm = Encapsulated PGM (reliable multicast)
            self.socket = self.zmq_context.socket(zmq.PUB)
            endpoint = f"epgm://{self.node_ip};{self.group}:{self.group_port}"
            self.socket.bind(endpoint)
            logger.debug(f"ZMQ multicast started at {endpoint}")
            while self._running:
                msg = self._local_info.create_heartbeat_message()  # your function
                # ZMQ expects bytes
                await self.socket.send(msg)
                await asyncio.sleep(self.interval)

        except Exception as e:
            logger.error(f"ZMQ multicast error: {e}")
            traceback.print_exc()

        finally:
            if self.socket:
                self.socket.close()
            logger.info("ZMQ multicast stopped")

    async def multicast_listener_loop(self):
        """Listen for heartbeat messages via ZeroMQ multicast (epgm)."""
        try:
            self.socket = self.zmq_context.socket(zmq.SUB)
            endpoint = f"epgm://{self.node_ip};{self.group}:{self.group_port}"
            self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
            self.socket.bind(endpoint)
            logger.debug(f"ZMQ multicast listener started at {endpoint}")
            while self._running:
                msg = await self.socket.recv()
                # Process the received heartbeat message
                # For example, update nodes_manager with the info
                # You need to implement parse_heartbeat_message
                node_info = parse_heartbeat_message(msg)
                self.nodes_manager.update_node_info(node_info)

        except Exception as e:
            logger.error(f"ZMQ multicast listener error: {e}")
            traceback.print_exc()

        finally:
            if self.socket:
                self.socket.close()
            logger.info("ZMQ multicast listener stopped")


    async def stop_node(self):
        """Stop the node's operations."""
        self._running = False
        await self.loop_manager.stop_node()
        logger.info("LanCom node has been stopped")