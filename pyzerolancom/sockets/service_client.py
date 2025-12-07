"""Client proxy for calling services."""
from typing import Optional, cast, Dict
import msgpack

from ..utils.log import logger
from ..nodes.lancom_node import LanComNode
from ..utils.msg import send_bytes_request

class ServiceProxy:
    """Client proxy for calling services."""

    @staticmethod
    def request(
        service_name: str,
        request: Dict,
    ) -> Optional[Dict]:
        """Send a request to a service and get the response."""
        if LanComNode.instance is None:
            raise ValueError("Lancom Node is not initialized")
        node = LanComNode.instance
        service_component = node.nodes_manager.get_service_info(service_name)
        if service_component is None:
            logger.warning("Service %s is not exist", service_name)
            return None
        addr = f"tcp://{service_component['ip']}:{service_component['port']}"
        request_bytes = msgpack.packb(request)
        if request_bytes is None:
            logger.error("Failed to pack request for service %s", service_name)
            return None
        response = node.loop_manager.submit_loop_task(
            send_bytes_request(addr, service_name, request_bytes),
            True,
        )
        return msgpack.unpackb(cast(bytes, response))
