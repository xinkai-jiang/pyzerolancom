from unittest.mock import Mock

import pytest

from pyzlc.sockets import subscriber_manager
from pyzlc.sockets.subscriber_manager import SubscriberManager


@pytest.fixture
def nodes_info_manager():
    manager = Mock()
    manager.local_node_info = {"ip": "192.168.1.100"}
    return manager


@pytest.fixture
def patched_subscriber_socket(monkeypatch):
    """Patch the Subscriber's connection and receive logic."""
    # The new Subscriber uses asyncio connections, not ZMQ.
    # For unit tests we just verify connect() dedup logic.
    pass


@pytest.fixture
def fake_loop_manager():
    class FakeLoopManager:
        def submit_loop_task(self, task):
            task.close()
            return Mock(done=lambda: False)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        subscriber_manager.TaskLoopManager,
        "get_instance",
        lambda: FakeLoopManager(),
    )
    return FakeLoopManager


@pytest.fixture
def patched_subscriber_class(monkeypatch):
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

    monkeypatch.setattr(subscriber_manager, "Subscriber", FakeSubscriber)
    return connected


@pytest.mark.unit
def test_subscriber_connect_skips_duplicate_urls(fake_loop_manager):
    sub = subscriber_manager.Subscriber("topic", lambda msg: None)
    sub.connect("tcp://127.0.0.1:1234")
    sub.connect("tcp://127.0.0.1:1234")

    assert len(sub.sub_urls) == 1


@pytest.mark.unit
def test_add_subscriber_connects_to_existing_publishers(
    nodes_info_manager,
    patched_subscriber_class,
):
    nodes_info_manager.get_publisher_info.return_value = [
        {"name": "topic", "ip": "127.0.0.1", "port": 5555}
    ]

    manager = SubscriberManager(Mock(), nodes_info_manager, "test_group")

    manager.add_subscriber("topic", lambda msg: None)

    assert patched_subscriber_class == ["tcp://127.0.0.1:5555"]
    assert "topic" in manager.subscriber_dict


@pytest.mark.unit
def test_check_new_node_connects_matching_subscriber_once(nodes_info_manager):
    sub = Mock()
    sub.sub_urls = []

    manager = SubscriberManager(Mock(), nodes_info_manager, "test_group")
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
def test_stop_unregisters_handler_and_closes_subscribers(nodes_info_manager):
    manager = SubscriberManager(Mock(), nodes_info_manager, "test_group")
    subscriber = Mock()
    manager.subscriber_dict["topic"] = subscriber

    manager.stop()

    nodes_info_manager.unregister_node_update_handler.assert_called_once_with(
        "*", manager.check_new_node
    )
    subscriber.close.assert_called_once_with()
