# Add these lines at the top of your pylancom/__init__.py
import asyncio
import platform

# Fix for Windows event loop to avoid ZMQ warnings
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore

# from pylancom.abstract_node import AbstractNode
from .nodes.lancom_node import LanComNode


def init_node(node_name: str, node_ip: str) -> LanComNode:
    if LanComNode.instance is None:
        return LanComNode(node_name, node_ip)
    if LanComNode.instance.name == node_name:
        raise ValueError(
            "Node is not initialized. Please call init_node() first."
        )
