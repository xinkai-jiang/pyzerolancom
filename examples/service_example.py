from typing import Callable
import traceback

import pyzerolancom
from pyzerolancom.utils.log import logger

def create_service_callback(service_name: str) -> Callable[[str], str]:
    """Create a service callback that echoes the received message."""
    def service_callback(msg: str) -> str:
        try:
            logger.info("Service %s received message: %s", service_name, msg)
            return msg
        except Exception as e:
            logger.error("Error in service %s: %s", service_name, e)
            traceback.print_exc()
            raise e
    return service_callback

if __name__ == "__main__":
    node = pyzerolancom.init_node("ServiceNode", "127.0.0.1")
    node.create_service("echo_service", create_service_callback("echo_service"))
    node.wait_for_service("echo_service")
    node.call("echo_service", "Hello, world!")
    node.stop_node()
