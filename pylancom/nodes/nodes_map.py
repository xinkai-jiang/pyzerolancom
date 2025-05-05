from __future__ import annotations

import abc
import asyncio
import concurrent.futures
import platform
import socket
import struct
import time
import traceback
from asyncio import AbstractEventLoop, get_running_loop
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, Dict, List, Optional, Union, cast

import msgpack
import zmq
import zmq.asyncio

from zmq.asyncio import Socket as AsyncSocket

from ..config import __COMPATIBILITY__
from ..lancom_type import (
    IPAddress,
    LanComMsg,
    NodeInfo,
    NodeReqType,
    Port,
    SocketInfo,
    TopicName,
)
from .lancom_socket import Subscriber
from ..utils.log import logger
from ..utils.msg import send_bytes_request


class NodesMap:
    def __init__(self):
        self.nodes_info: Dict[str, NodeInfo] = {}
        self.nodes_info_id: Dict[str, int] = {}
        self.nodes_heartbeat: Dict[str, str] = {}
        self.publishers_dict: Dict[str, SocketInfo] = {}
        self.services_dict: Dict[str, SocketInfo] = {}

    def check_node(self, node_id: str) -> bool:
        return node_id in self.nodes_info

    def check_info(self, node_id: str, info_id: int) -> bool:
        return self.nodes_info_id.get(node_id, "") == info_id

    def check_heartbeat(self, node_id: str, info_id: int) -> bool:
        return self.check_node(node_id) and self.check_info(node_id, info_id)

    def update_node(self, node_id: str, node_info: NodeInfo):
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
        self.nodes_info.pop(node_id, None)
        self.nodes_info_id.pop(node_id, None)

    def get_publisher_info(self, topic_name: TopicName) -> List[SocketInfo]:
        publishers: List[SocketInfo] = []
        for pub_info in self.publishers_dict.values():
            if pub_info["name"] == topic_name:
                publishers.append(pub_info)
        return publishers

    def get_service_info(self, service_name: str) -> Optional[SocketInfo]:
        for service in self.services_dict.values():
            if service["name"] == service_name:
                return service
        return None
