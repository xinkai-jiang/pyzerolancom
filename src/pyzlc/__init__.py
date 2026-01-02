# Add these lines at the top of your pyzlc/__init__.py
from __future__ import annotations
import asyncio
import platform
from typing import Callable, Any
import time

# from pyzlc.abstract_node import AbstractNode
from .nodes.lancom_node import LanComNode
from .sockets.publisher import Publisher
from .utils.log import _logger


# Fix for Windows event loop to avoid ZMQ warnings
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore


def init(node_name: str, node_ip: str) -> None:
    """Initialize the LanCom node singleton."""
    if LanComNode.instance is not None:
        raise ValueError("Node is already initialized.")
    LanComNode.init(node_name, node_ip)


def sleep(duration: float) -> None:
    """Sleep for the specified duration in seconds."""
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        _logger.debug("Sleep interrupted by user")
        LanComNode.get_instance().stop_node()


def spin() -> None:
    """Spin the LanCom node to process incoming messages."""
    try:
        LanComNode.get_instance().loop_manager.spin()
    except KeyboardInterrupt:
        _logger.debug("LanCom node interrupted by user")
        LanComNode.get_instance().stop_node()
    finally:
        _logger.info("LanCom node has been stopped")

def call(
    service_name: str,
    request: Any,
) -> Any:
    """Call a service with the specified name and request."""
    return LanComNode.get_instance().call(
        service_name, request
    )

def register_service_handler(
    service_name: str,
    callback: Callable,
) -> None:
    """Create a service with the specified name and callback."""
    LanComNode.get_instance().register_service_handler(service_name, callback)


def register_subscriber_handler(
    topic_name: str,
    callback: Callable,
) -> None:
    """Create a subscriber for the specified topic."""
    LanComNode.get_instance().register_subscriber_handler(topic_name, callback)


def wait_for_service(
    service_name: str,
    timeout: float = 5.0,
    check_interval: float = 0.1,
) -> None:
    """Wait for a service to become available."""
    LanComNode.get_instance().wait_for_service(service_name, timeout, check_interval)

info = _logger.info
debug = _logger.debug
warning = _logger.warning
error = _logger.error
remote_log = _logger.remote_log
