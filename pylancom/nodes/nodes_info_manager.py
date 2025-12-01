from __future__ import annotations

from typing import Dict, List, Optional

from ..utils.lancom_type import (
    NodeInfo,
    SocketInfo,
    TopicName,
)

from ..utils.log import logger


class NodesInfoManager:
    """Manages information about nodes in the network."""
    def __init__(self):
        self.nodes_info: Dict[str, NodeInfo] = {}
        self.nodes_info_id: Dict[str, int] = {}
        self.nodes_heartbeat: Dict[str, str] = {}
        self.publishers_dict: Dict[str, SocketInfo] = {}
        self.services_dict: Dict[str, SocketInfo] = {}

    def check_node(self, node_id: str) -> bool:
        """Check if a node with the given ID exists."""
        return node_id in self.nodes_info

    def check_info(self, node_id: str, info_id: int) -> bool:
        """Check if the info ID for a given node matches the provided info ID."""
        return self.nodes_info_id.get(node_id, "") == info_id

    def check_heartbeat(self, node_id: str, info_id: int) -> bool:
        """Check if the heartbeat for a given node is valid."""
        return self.check_node(node_id) and self.check_info(node_id, info_id)

    def update_node(self, node_id: str, node_info: NodeInfo):
        """Update or add a node's information."""
        if node_id not in self.nodes_info:
            logger.debug(f"Node {node_info['name']} has been registered")
        for pub_info in node_info["pubList"]:
            if pub_info["socketID"] not in self.publishers_dict:
                self.publishers_dict[pub_info["socketID"]] = pub_info
        for service_info in node_info["srvList"]:
            if service_info["socketID"] not in self.services_dict:
                self.services_dict[service_info["socketID"]] = service_info
        self.nodes_info[node_id] = node_info
        self.nodes_info_id[node_id] = node_info["infoID"]

    def remove_node(self, node_id: str) -> None:
        """Remove a node's information."""
        self.nodes_info.pop(node_id, None)
        self.nodes_info_id.pop(node_id, None)

    def get_publisher_info(self, topic_name: TopicName) -> List[SocketInfo]:
        """Get a list of publisher socket information for a given topic name."""
        publishers: List[SocketInfo] = []
        for pub_info in self.publishers_dict.values():
            if pub_info["name"] == topic_name:
                publishers.append(pub_info)
        return publishers

    def get_service_info(self, service_name: str) -> Optional[SocketInfo]:
        """Get the service socket information for a given service name."""
        for service in self.services_dict.values():
            if service["name"] == service_name:
                return service
        return None
