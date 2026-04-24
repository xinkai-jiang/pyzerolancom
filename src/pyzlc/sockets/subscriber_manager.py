import traceback
from typing import Callable, Dict, List, Any, Optional
from concurrent.futures import Future
import zmq
import msgpack

from ..utils.node_info import NodeInfo

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
        self.published_urls: List[str] = []
        # self._listen_future: Optional[Future] = None
        self._receive_future: Optional[Future] = None
        # self._listen_future = self.loop_manager.submit_loop_task(self.listen_loop())

    def connect(self, url: str) -> None:
        """Connect to a publisher's socket."""
        self._socket.connect(url)
        self.connected = True
        self.published_urls.append(url)
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
    #                 if _url not in self.published_urls:
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

    def __init__(self, loop_manager: TaskLoopManager, nodes_info_manager: NodesInfoManager) -> None:
        # self.subscribers: List[Subscriber] = []
        self.subscriber_dict: Dict[str, Subscriber] = {}
        self.loop_manager = loop_manager
        self.nodes_info_manager = nodes_info_manager
        self.nodes_info_manager.register_node_update_handler("*", self.check_new_node)

    def add_subscriber(
        self,
        topic_name: str,
        callback: Callable[[Any], None],
        buffer_size: int = 1000,
        conflate: bool = False
    ) -> None:
        """Add a new subscriber and start its listening and receiving loops."""
        subscriber = Subscriber(topic_name, callback, buffer_size, conflate)
        # self.subscribers.append(subscriber)
        self.subscriber_dict[topic_name] = subscriber

    def on_shutdown(self) -> None:
        """Shutdown all subscriber sockets."""
        for subscriber in self.subscriber_dict.values():
            subscriber.close()

    def check_new_node(self, node_info: NodeInfo) -> None:
        """Check if a new node has published the subscribed topic and connect to it."""
        for topic in node_info["topics"]:
            if topic["name"] in self.subscriber_dict:
                _url = f"tcp://{node_info['ip']}:{topic['port']}"
                if _url not in self.subscriber_dict[topic["name"]].published_urls:
                    self.subscriber_dict[topic["name"]].connect(_url)