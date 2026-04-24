from unittest.mock import Mock

import pytest

from pyzlc.sockets import subscriber_manager
from pyzlc.sockets.subscriber_manager import SubscriberManager


@pytest.mark.unit
def test_subscriber_connect_skips_duplicate_urls(monkeypatch):
    socket = Mock()
    socket.connect = Mock()

    class FakeLoopManager:
        def submit_loop_task(self, task):
            task.close()
            return Mock(done=lambda: False)

    class FakeSocketManager:
        def create_async_socket(self, socket_type):
            return socket

    monkeypatch.setattr(
        subscriber_manager.ZMQSocketManager,
        "get_instance",
        lambda: FakeSocketManager(),
    )
    monkeypatch.setattr(
        subscriber_manager.TaskLoopManager,
        "get_instance",
        lambda: FakeLoopManager(),
    )

    sub = subscriber_manager.Subscriber("topic", lambda msg: None)
    sub.connect("tcp://127.0.0.1:1234")
    sub.connect("tcp://127.0.0.1:1234")

    socket.connect.assert_called_once_with("tcp://127.0.0.1:1234")


@pytest.mark.unit
def test_add_subscriber_connects_to_existing_publishers(monkeypatch):
    connected = []

    class FakeSubscriber:
        def __init__(self, topic_name, callback, buffer_size, conflate):
            self.name = topic_name
            self.sub_urls = []

        def connect(self, url):
            connected.append(url)
            self.sub_urls.append(url)

        def close(self):
            pass

    nodes_info_manager = Mock()
    nodes_info_manager.get_publisher_info.return_value = [
        {"name": "topic", "ip": "127.0.0.1", "port": 5555}
    ]

    monkeypatch.setattr(subscriber_manager, "Subscriber", FakeSubscriber)
    manager = SubscriberManager(Mock(), nodes_info_manager)

    manager.add_subscriber("topic", lambda msg: None)

    assert connected == ["tcp://127.0.0.1:5555"]
    assert "topic" in manager.subscriber_dict


@pytest.mark.unit
def test_check_new_node_connects_matching_subscriber_once():
    sub = Mock()
    sub.sub_urls = []

    nodes_info_manager = Mock()
    manager = SubscriberManager(Mock(), nodes_info_manager)
    manager.subscriber_dict["topic"] = sub
    node_info = {
        "name": "node",
        "nodeID": "node-id",
        "infoID": 1,
        "ip": "127.0.0.1",
        "topics": [{"name": "topic", "ip": "127.0.0.1", "port": 6000}],
        "services": [],
    }

    manager.check_new_node(node_info)
    sub.sub_urls.append("tcp://127.0.0.1:6000")
    manager.check_new_node(node_info)

    sub.connect.assert_called_once_with("tcp://127.0.0.1:6000")


@pytest.mark.unit
def test_stop_unregisters_handler_and_closes_subscribers():
    nodes_info_manager = Mock()
    manager = SubscriberManager(Mock(), nodes_info_manager)
    subscriber = Mock()
    manager.subscriber_dict["topic"] = subscriber

    manager.stop()

    nodes_info_manager.unregister_node_update_handler.assert_called_once_with(
        "*", manager.check_new_node
    )
    subscriber.close.assert_called_once_with()
