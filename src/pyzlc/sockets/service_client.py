"""Client proxy for calling services."""

from typing import Optional, Any

from ..nodes.lancom_node import LanComNode
from ..utils.log import _logger
from ..utils.msg import ResponseT, RequestT
from ..utils.msg import send_request


async def zlc_request_async(
    service_name: str,
    request: RequestT,
    timeout: float,
    group_name: Optional[str] = None,
) -> Optional[ResponseT]:
    """Send an asynchronous request to a service and get the response."""
    nodes_manager = LanComNode.get_instance(group_name).nodes_info_manager
    service_info = nodes_manager.get_service_info(service_name)
    if service_info is None:
        _logger.warning("Service %s is not exist", service_name)
        return None
    addr = f"tcp://{service_info['ip']}:{service_info['port']}"
    return await send_request(addr, service_name, request, timeout)


def zlc_request(
    service_name: str,
    request: RequestT,
    timeout: float,
    group_name: Optional[str] = None,
) -> Optional[ResponseT]:
    """Send a request to a service and get the response."""
    return LanComNode.get_instance(group_name).loop_manager.submit_loop_task_and_wait(
        zlc_request_async(service_name, request, timeout, group_name)
    )

def call(
    service_name: str,
    request: Any,
    timeout: float = 2.0,
    group_name: Optional[str] = None,
) -> Any:
    """Call a service with the specified name and request."""
    return zlc_request(service_name, request, timeout, group_name)


async def async_call(
    service_name: str,
    request: Any,
    timeout: float = 2.0,
    group_name: Optional[str] = None,
) -> Any:
    """Asynchronously call a service with the specified name and request."""
    return await zlc_request_async(service_name, request, timeout, group_name)