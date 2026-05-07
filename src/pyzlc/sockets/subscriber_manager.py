import traceback
from typing import Callable, Dict, List, Any, Optional
from concurrent.futures import Future
import msgpack

from ..utils.node_info import NodeInfo, SocketInfo

from ..utils.log import _logger
from ..nodes.loop_manager import TaskLoopManager
from ..nodes.nodes_info_manager import NodesInfoManager
from ..transports.protocol import (
    TOPIC_PUBLISH,
    TOPIC_SUBSCRIBE,
    TOPIC_UNSUBSCRIBE,
    decode_topic_publish,
    encode_frame,
    encode_topic_subscribe,
    read_frame,
)
from ..transports.tcp_server import encode_topic_publish


class Subscriber:
    """Subscribes to messages from a topic via asyncio TCP or IPC."""

    def __init__(
        self,
        topic_name: str,
        callback: Callable[[Any], None],
        buffer_size: int = 1000,
        conflate: bool = False,
    ):
        self.name = topic_name
        self.callback = callback
        self.conflate = conflate
        self.running: bool = True
        self.connected: bool = False
        self.sub_urls: List[str] = []
        self._receive_future: Optional[Future] = None
        # Track active reader tasks for cleanup
        self._reader_tasks: list = []

    async def _connect_and_receive(
        self, url: str, is_ipc: bool = False
    ) -> None:
        """Connect to a publisher and start receiving messages."""
        import asyncio

        reader = None
        writer = None
        try:
            if is_ipc:
                reader, writer = await asyncio.open_unix_connection(url)
            else:
                host, port_str = url.replace("tcp://", "").split(":")
                reader, writer = await asyncio.open_connection(host, int(port_str))

            # Send subscription request
            sub_payload = encode_topic_subscribe(self.name)
            writer.write(encode_frame(TOPIC_SUBSCRIBE, sub_payload))
            await writer.drain()

            _logger.info(
                "Subscriber %s connected to %s", self.name, url
            )

            # Receive loop
            while self.running:
                result = await read_frame(reader)
                if result is None:
                    break
                msg_type, payload = result
                if msg_type == TOPIC_PUBLISH:
                    topic_name, data = decode_topic_publish(payload)
                    if topic_name == self.name:
                        self.callback(msgpack.unpackb(data))
        except asyncio.CancelledError:
            pass
        except (ConnectionError, OSError) as e:
            _logger.debug(
                "Subscriber %s disconnected from %s: %s",
                self.name, url, e,
            )
        except Exception as e:
            _logger.error(
                "Error from topic %s subscriber: %s", self.name, e
            )
            traceback.print_exc()
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    def connect(self, url: str) -> None:
        """Connect to a publisher's socket."""
        if url in self.sub_urls:
            return
        self.connected = True
        self.sub_urls.append(url)
        is_ipc = url.startswith("ipc://")
        connect_url = url.replace("ipc://", "") if is_ipc else url

        task = TaskLoopManager.get_instance().submit_loop_task(
            self._connect_and_receive(connect_url, is_ipc)
        )
        self._reader_tasks.append(task)

    def close(self) -> None:
        """Close the subscriber."""
        self.running = False
        for task in self._reader_tasks:
            task.cancel()
        self._reader_tasks.clear()
        _logger.info("Subscriber %s has been closed", self.name)


class SubscriberManager:
    """Manages multiple subscribers."""

    def __init__(self, loop_manager: TaskLoopManager, nodes_info_manager: NodesInfoManager, group_name: str) -> None:
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
            return f"ipc:///tmp/zlc/{self.group_name}/{info['name']}/topic.sock"
        return f"tcp://{info['ip']}:{info['port']}"

    def add_subscriber(
        self,
        topic_name: str,
        callback: Callable[[Any], None],
        buffer_size: int = 1000,
        conflate: bool = False
    ) -> None:
        """Add a new subscriber and start its receive loops."""
        subscriber = Subscriber(topic_name, callback, buffer_size, conflate)
        pub_infos = self.nodes_info_manager.get_publisher_info(topic_name)
        for info in pub_infos:
            _url = self._get_connect_url(info)
            subscriber.connect(_url)
        self.subscriber_dict[topic_name] = subscriber

    def stop(self) -> None:
        """Shutdown all subscribers."""
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
