from __future__ import annotations

from typing import Optional, Dict

from .loop_manager import TaskLoopManager
from .multicast import MulticastWorker
from .nodes_info_manager import NodesInfoManager
from ..sockets.service_manager import ServiceManager
from ..sockets.subscriber_manager import SubscriberManager
from ..transports.tcp_server import TcpServerManager
from ..utils.msg import Empty
from ..utils.log import _logger
from ..utils.node_info import NodeInfo


class LanComNode:
    """Represents a LanCom node in the network."""

    default_instance: Optional[LanComNode] = None
    node_instances: Dict[str, LanComNode] = {}

    @classmethod
    def get(cls, group_name: Optional[str] = None) -> Optional[LanComNode]:
        """Get the singleton instance of LanComNode."""
        if group_name is None:
            return cls.default_instance
        else:
            return cls.node_instances.get(group_name)

    @classmethod
    def get_instance(cls, group_name: Optional[str] = None) -> LanComNode:
        """Get the singleton instance of LanComNode, raise error if not initialized."""
        node = cls.get(group_name)
        if node is None:
            raise ValueError("LanComNode is not initialized. Please call init() first.")
        return node

    @classmethod
    def stop_all_nodes(cls):
        """Stop all LanCom nodes, including sub-group nodes."""
        if not cls.node_instances and cls.default_instance is None:
            return  # Already shut down
        for group_name, node in list(cls.node_instances.items()):
            node.stop_node()
            _logger.debug(f"Sub-node for group '{group_name}' has been stopped.")
        cls.node_instances.clear()
        cls.default_instance = None
        if TaskLoopManager.instance is not None:
            TaskLoopManager.instance.stop()

    @classmethod
    def init(
        cls,
        node_name: str,
        node_ip: str,
        group: str,
        group_port: int,
        group_name: str,
        default_group: bool = True,
    ) -> None:
        if group_name in cls.node_instances:
            raise ValueError(
                f"Node for group '{group_name}' is already initialized."
            )
        else:
            cls.node_instances[group_name] = LanComNode(
                node_name, node_ip, group, group_port, group_name
            )
        if default_group:
            if cls.default_instance is None:
                cls.default_instance = cls.node_instances[group_name]
            else:
                _logger.warning(
                    "Default LanComNode instance is already set. "
                    "The first initialized node will be used as the default instance."
                )

    def __init__(
        self,
        node_name: str,
        node_ip: str,
        group: str,
        group_port: int,
        group_name: str,
    ) -> None:
        self.name = node_name
        self.node_ip = node_ip
        self.group = group
        self.group_port = group_port
        self.group_name = group_name
        self.loop_manager: TaskLoopManager = TaskLoopManager.get_instance()
        self.nodes_info_manager: NodesInfoManager = NodesInfoManager(
            node_name, node_ip, self.loop_manager
        )
        # Single TCP server that multiplexes all pub/sub and service traffic
        self.tcp_server = TcpServerManager(self.node_ip)
        self.loop_manager.submit_loop_task(self.tcp_server.start())
        self.service_manager = ServiceManager(
            self.tcp_server, self.loop_manager
        )
        self.subscriber_manager = SubscriberManager(self.loop_manager, self.nodes_info_manager, self.group_name)
        self.multicast_worker = MulticastWorker(
            local_info=self.nodes_info_manager.local_node_info,
            service_port=lambda: self.tcp_server.port,
            group=self.group,
            group_port=self.group_port,
            group_name=self.group_name,
            loop_manager=self.loop_manager,
            nodes_info_manager=self.nodes_info_manager,
        )

    def start_node(self):
        """Start the node's operations."""
        _logger.debug("Starting LanCom node...")
        self.running: bool = True
        # Start multicast worker (runs in separate threads)
        self.multicast_worker.start()
        # Add async heartbeat check to the event loop
        self.heartbeat_future = self.loop_manager.submit_loop_task(
            self.nodes_info_manager.check_heartbeat()
        )

    def _get_node_info_handler(self, request: Empty) -> NodeInfo:
        return self.nodes_info_manager.local_node_info

    def stop_node(self):
        """Stop the node's operations."""
        _logger.debug("Stopping LanCom node...")
        self.running = False
        self.service_manager.stop()
        self.subscriber_manager.stop()
        self.multicast_worker.stop()
        self.heartbeat_future.cancel()
        self.tcp_server.close()
        LanComNode.node_instances.pop(self.group_name, None)
        if LanComNode.default_instance is self:
            LanComNode.default_instance = None
        _logger.debug("LanCom node has been stopped")
