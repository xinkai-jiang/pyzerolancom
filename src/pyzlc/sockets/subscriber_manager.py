import traceback
from typing import Callable, Dict, List, Any, Optional
from concurrent.futures import Future
import zmq
import msgpack

from ..utils.node_info import NodeInfo, SocketInfo

from ..nodes.zmq_socket_manager import ZMQSocketManager
from ..utils.log import _logger
from ..nodes.loop_manager import TaskLoopManager
from ..nodes.nodes_info_manager import NodesInfoManager

class Subscriber:
    """Subscribes to messages from a topic."""

    def __init__(
        self,
        topic_name: str,
        callback: Callable[[Any], None],
        buffer_size: int = 1000,
        conflate: bool = False,
    ):
        self._socket = ZMQSocketManager.get_instance().create_async_socket(zmq.SUB)
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        if conflate:
            self._socket.setsockopt(zmq.CONFLATE, 1)
        else:
            self._socket.setsockopt(zmq.SNDHWM, buffer_size)
        self.name = topic_name
        self.callback = callback
        self.running: bool = True
        self.connected: bool = False
        self.sub_urls: List[str] = []
        # self._listen_future: Optional[Future] = None
        self._receive_future: Optional[Future] = None
        # self._listen_future = self.loop_manager.submit_loop_task(self.listen_loop())

    def connect(self, url: str) -> None:
        """Connect to a publisher's socket."""
        if url in self.sub_urls:
            return
        self._socket.connect(url)
        self.connected = True
        self.sub_urls.append(url)
        _logger.info("Subscriber %s is connected to %s", self.name, url)
        if self._receive_future is None or self._receive_future.done():
            self._receive_future = TaskLoopManager.get_instance().submit_loop_task(
                self.receive_loop()
            )

    # async def listen_loop(self) -> None:
    #     """Listens for new publishers and connects to them."""
    #     _logger.info("Subscriber %s is listening ...", self.name)
    #     while self.running:
    #         try:
    #             publishers = self.nodes_info_manager.get_publisher_info(self.name)
    #             for pub_info in publishers:
    #                 _url = f"tcp://{pub_info['ip']}:{pub_info['port']}"
    #                 if _url not in self.sub_urls:
    #                     self.connect(_url)
    #             await asyncio.sleep(0.5)
    #         except Exception as e:
    #             _logger.error("Error from topic %s listener: %s", self.name, e)
    #             traceback.print_exc()
    #             raise e

    async def receive_loop(self) -> None:
        """Listens for incoming messages on the subscribed topic."""
        _logger.info("Subscriber %s is subscribing ...", self.name)
        while self.running:
            try:
                # events = await self._socket.poll()
                # if not events:
                #     continue
                msg = await self._socket.recv()
                self.callback(msgpack.unpackb(msg))
            # except asyncio.CancelledError:
            #     _logger.info("Receive loop for subscriber %s cancelled...", self.name)
            #     break
            # except KeyboardInterrupt:
            #     _logger.info("Receive loop for subscriber %s interrupted by user...", self.name)
            #     break
            except Exception as e:
                _logger.error("Error from topic %s subscriber: %s", self.name, e)
                traceback.print_exc()
                raise e

    def close(self) -> None:
        """Close the subscriber socket."""
        self.running = False
        if self._receive_future is not None:
            self._receive_future.cancel()
        self._socket.close()
        _logger.info("Subscriber %s has been closed", self.name)


class SubscriberManager:
    """Manages multiple subscribers."""

    def __init__(self, loop_manager: TaskLoopManager, nodes_info_manager: NodesInfoManager, group_name: str) -> None:
        # self.subscribers: List[Subscriber] = []
        self.subscriber_dict: Dict[str, Subscriber] = {}
        self.loop_manager = loop_manager
        self.nodes_info_manager = nodes_info_manager
        self.group_name = group_name
        self.local_ip = nodes_info_manager.local_node_info["ip"]
        self.nodes_info_manager.register_node_update_handler("*", self.check_new_node)

    def _get_connect_url(self, info: SocketInfo) -> str:
        """Determine the connection URL for a publisher info entry.

        If the publisher is on the same host, use IPC for better performance.
        Otherwise, use TCP.
        """
        if info["ip"] == self.local_ip:
            return f"ipc://{self.group_name}/{info['name']}"
        return f"tcp://{info['ip']}:{info['port']}"

    def add_subscriber(
        self,
        topic_name: str,
        callback: Callable[[Any], None],
        buffer_size: int = 1000,
        conflate: bool = False
    ) -> None:
        """Add a new subscriber and start its listening and receiving loops."""
        subscriber = Subscriber(topic_name, callback, buffer_size, conflate)
        pub_infos = self.nodes_info_manager.get_publisher_info(topic_name)
        for info in pub_infos:
            _url = self._get_connect_url(info)
            subscriber.connect(_url)
        self.subscriber_dict[topic_name] = subscriber

    def stop(self) -> None:
        """Shutdown all subscriber sockets."""
        self.nodes_info_manager.unregister_node_update_handler("*", self.check_new_node)
        for subscriber in self.subscriber_dict.values():
            subscriber.close()

    def check_new_node(self, node_info: NodeInfo) -> None:
        """Check if a new node has published the subscribed topic and connect to it."""
        for topic in node_info["topics"]:
            if topic["name"] in self.subscriber_dict:
                _url = self._get_connect_url(topic)
                if _url not in self.subscriber_dict[topic["name"]].sub_urls:
                    self.subscriber_dict[topic["name"]].connect(_url)
