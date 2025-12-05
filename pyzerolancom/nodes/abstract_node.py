# from __future__ import annotations

# import abc
# import asyncio
# import concurrent.futures
# import json
# import platform
# import socket
# import struct
# import traceback
# from asyncio import get_running_loop
# from typing import Any, Coroutine, Union, cast

# import zmq
# import zmq.asyncio
# from zmq.asyncio import Context as AsyncContext

# from ..config import __COMPATIBILITY__
# from ..lancom_type import IPAddress, LanComMsg, NodeInfo, NodeReqType, Port
# from ..utils.log import logger
# from ..utils.msg import send_bytes_request
# from .loop_manager import LanComLoopManager
# from .nodes_map import NodesMap


# class AbstractNode(abc.ABC):
#     def __init__(
#         self,
#         node_name: str,
#         node_ip: IPAddress,
#         multicast_addr: IPAddress = "224.0.0.1",
#         multicast_port: int = 7720,
#     ) -> None:
#         super().__init__()
#         self.node_name = node_name
#         self.node_ip = node_ip
#         self.multicast_addr = multicast_addr
#         self.multicast_port = multicast_port
#         # for running on Windows localhost, use a different multicast address
#         if self.node_ip == "127.0.0.1" and platform.system() == "Windows":
#             self.multicast_addr = "239.255.255.250"
#         self.zmq_context: AsyncContext = zmq.asyncio.Context()
#         self.running = False
#         self.loop_manager = LanComLoopManager()
#         self.nodes_map = NodesMap()
#         # self.loop: Optional[AbstractEventLoop] = None
#         # # start spin task
#         # self.loop_manager.submit_loop_task(self.spin_task)
#         # while not self.running:
#         #     time.sleep(0.05)

#     async def listen_nodes_loop(self):
#         """Asynchronously listens for multicast messages from other nodes."""
#         try:
#             logger.debug("Starting multicast listening")
#             _socket = socket.socket(
#                 socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
#             )
#             _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#             # _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
#             group = socket.inet_aton(self.multicast_addr)
#             _socket.setsockopt(
#                 socket.IPPROTO_IP,
#                 socket.IP_ADD_MEMBERSHIP,
#                 struct.pack("4sL", group, socket.INADDR_ANY),
#             )
#             _socket.bind(("", self.multicast_port))
#             while self.running:
#                 try:
#                     data, addr = await get_running_loop().run_in_executor(
#                         self.loop_manager._executor, _socket.recvfrom, 1024
#                     )
#                     await self.process_heartbeat(data, addr[0])
#                 except Exception as e:
#                     logger.error(f"Error receiving multicast message: {e}")
#                     traceback.print_exc()
#                 await asyncio.sleep(0.5)
#         except Exception as e:
#             logger.error(f"Listening loop error: {e}")
#             traceback.print_exc()
#         finally:
#             _socket.close()
#             logger.info("Multicast receiving has been stopped")

#     async def process_heartbeat(self, data: bytes, ip: IPAddress) -> None:
#         """Processes received multicast messages and prints them."""
#         try:
#             if data[:6] != b"LANCOM":
#                 return
#             if data[6:8] != __COMPATIBILITY__:
#                 logger.warning(f"Incompatible version {data[6:9]}")
#                 return
#             node_id = data[9:45].decode()
#             node_port = int.from_bytes(data[-6:-4], "big")
#             node_info_id = int.from_bytes(data[-4:], "big")
#             # add a new node to the map
#             if self.nodes_map.check_heartbeat(node_id, node_info_id):
#                 return
#             node_info_bytes = await self.send_request(
#                 NodeReqType.NODE_INFO.value,
#                 ip,
#                 node_port,
#                 LanComMsg.EMPTY.value,
#             )
#             if node_info_bytes == LanComMsg.TIMEOUT.value.encode():
#                 return
#             node_info = cast(NodeInfo, json.loads(node_info_bytes))
#             self.nodes_map.update_node(node_id, node_info)
#             return
#         except Exception as e:
#             logger.error(f"Error processing received message: {e}")
#             traceback.print_exc()

#     async def send_request(
#         self,
#         service_name: str,
#         ip: IPAddress,
#         port: Port,
#         msg: str,
#     ) -> bytes:
#         """Sends a request to another node."""
#         addr = f"tcp://{ip}:{port}"
#         result = await send_bytes_request(
#             addr,
#             service_name,
#             msg.encode(),
#         )
#         return result

#     def submit_loop_task(
#         self,
#         task: Coroutine,
#         block: bool = False,
#     ) -> Union[concurrent.futures.Future, Any]:
#         if not self.loop_manager._loop:
#             raise RuntimeError("The event loop is not running")
#         future = asyncio.run_coroutine_threadsafe(
#             task, self.loop_manager._loop
#         )
#         if block:
#             return future.result()
#         return future
