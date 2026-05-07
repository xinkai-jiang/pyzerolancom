from unittest.mock import Mock

import pytest

from pyzlc.nodes import lancom_node
from pyzlc.nodes.lancom_node import LanComNode


@pytest.fixture(autouse=True)
def reset_lancom_node_state():
    LanComNode.node_instances.clear()
    LanComNode.default_instance = None
    yield
    LanComNode.node_instances.clear()
    LanComNode.default_instance = None


@pytest.mark.unit
def test_init_sets_default_and_rejects_duplicate(monkeypatch):
    def fake_init(self, node_name, node_ip, group, group_port, group_name):
        self.name = node_name
        self.node_ip = node_ip
        self.group = group
        self.group_port = group_port
        self.group_name = group_name

    monkeypatch.setattr(LanComNode, "__init__", fake_init)

    LanComNode.init("node", "127.0.0.1", "224.0.0.1", 7720, "group")

    assert LanComNode.default_instance is LanComNode.node_instances["group"]
    with pytest.raises(ValueError):
        LanComNode.init("node", "127.0.0.1", "224.0.0.1", 7720, "group")


@pytest.mark.unit
def test_stop_node_unregisters_default_instance():
    node = LanComNode.__new__(LanComNode)
    node.group_name = "group"
    node.service_manager = Mock()
    node.subscriber_manager = Mock()
    node.multicast_worker = Mock()
    node.heartbeat_future = Mock()
    node.tcp_server = Mock()
    node.loop_manager = Mock()
    LanComNode.node_instances["group"] = node
    LanComNode.default_instance = node

    node.stop_node()

    assert "group" not in LanComNode.node_instances
    assert LanComNode.default_instance is None
    node.service_manager.stop.assert_called_once_with()
    node.subscriber_manager.stop.assert_called_once_with()
    node.multicast_worker.stop.assert_called_once_with()
    node.heartbeat_future.cancel.assert_called_once_with()


@pytest.mark.unit
def test_stop_all_nodes_iterates_over_copy_and_stops_loop(monkeypatch):
    stopped = []

    class FakeLoopManager:
        def stop(self):
            stopped.append("loop")

    fake_loop = FakeLoopManager()
    monkeypatch.setattr(lancom_node.TaskLoopManager, "instance", fake_loop)

    def make_node(group_name):
        node = LanComNode.__new__(LanComNode)
        node.group_name = group_name

        def stop_node():
            stopped.append(group_name)
            LanComNode.node_instances.pop(group_name, None)

        node.stop_node = stop_node
        return node

    LanComNode.node_instances["a"] = make_node("a")
    LanComNode.node_instances["b"] = make_node("b")

    LanComNode.stop_all_nodes()

    assert stopped == ["a", "b", "loop"]
    assert LanComNode.node_instances == {}
    assert LanComNode.default_instance is None
