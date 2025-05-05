from __future__ import annotations
import abc
from typing import Optional, Coroutine, Any
import zmq
from zmq.asyncio import Context as AsyncContext
import zmq.asyncio

from ..lancom_type import (
    AsyncSocket,
    NodeInfo,
    HashIdentifier,
    SocketInfo,
)
from ..utils.msg import create_hash_identifier
from ..utils.msg import get_socket_addr
from .nodes_map import NodesMap
from .loop_manager import LanComLoopManager
from ..lancom_type import IPAddress


class LanComNodeBase(abc.ABC):
    instance: Optional[LanComNodeBase] = None

    def __init__(
        self,
        node_name: str,
        node_ip: IPAddress,
        multicast_addr: IPAddress = "224.0.0.1",
        multicast_port: int = 7720,
    ) -> None:
        super().__init__()
        self.multicast_addr = multicast_addr
        self.multicast_port = multicast_port
        self._local_info: NodeInfo = {
            "name": node_name,
            "nodeID": create_hash_identifier(),
            "ip": node_ip,
            "type": "",
            "infoID": 0,
            "pubList": [],
            "subList": [],
            "srvList": [],
        }
        self.zmq_context: AsyncContext = zmq.asyncio.Context()
        self.nodes_map: NodesMap = NodesMap()
        self.loop_manager: LanComLoopManager = LanComLoopManager()
        self._running: bool = False

    @abc.abstractmethod
    def create_socket(self, socket_type: int) -> AsyncSocket:
        raise NotImplementedError

    @property
    def local_info(self) -> NodeInfo:
        return self._local_info

    @property
    def name(self) -> str:
        return self._local_info["name"]

    @property
    def id(self) -> HashIdentifier:
        return self._local_info["nodeID"]

    @property
    def ip(self) -> IPAddress:
        return self._local_info["ip"]

    # @abc.abstractmethod
    # def submit_loop_task(
    #     self,
    #     task: Coroutine[Any, Any, Any],
    #     name: str,
    #     interval: float = 0.1,
    # ) -> None:
    #     raise NotImplementedError



class LanComSocketBase(abc.ABC):

    def __init__(
        self,
        name: str,
        socket_type: int,
        with_local_namespace: bool = False,
    ) -> None:
        if LanComNodeBase.instance is None:
            raise RuntimeError("LanComNode is not initialized.")
        self.node = LanComNodeBase.instance
        self.loop_manager = self.node.loop_manager
        socket_name = name
        if with_local_namespace:
            socket_name = f"{self.node.local_info['name']}_{socket_name}"
        self.zmq_socket = self.node.create_socket(socket_type)
        ip, port = get_socket_addr(self.zmq_socket)
        self.socket_info: SocketInfo = {
            "name": socket_name,
            "socketID": create_hash_identifier(),
            "nodeID": ip,
            "type": socket_type,
            "ip": ip,
            "port": port,
        }
        self.running: bool = False

    @property
    def info(self) -> SocketInfo:
        return self.socket_info

    @property
    def name(self) -> str:
        return self.socket_info["name"]

    def shutdown(self) -> None:
        self.running = False
        self.on_shutdown()

    @abc.abstractmethod
    def on_shutdown(self):
        raise NotImplementedError