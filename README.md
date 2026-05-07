# pyzlc

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-green)
[![PyPI version](https://badge.fury.io/py/pyzlc.svg)](https://badge.fury.io/py/pyzlc)

`pyzlc` is a lightweight, ROS-like communication toolkit for Python processes on trusted local networks. It uses UDP multicast for automatic node discovery and asyncio TCP streams for pub/sub topics and request/response services, so small nodes can find each other on the same host or on the same multicast-capable LAN without a central master.

## When To Use pyzlc

- You want ROS-style topics and services without installing or running ROS.
- You are building small Python nodes for robotics, lab automation, sensor streaming, demos, or local distributed tools.
- Your processes run on one host or on multiple hosts in the same trusted LAN.
- You want automatic discovery instead of hard-coding peer addresses in every script.

`pyzlc` is intentionally smaller than ROS. It does not provide ROS message generation, bags, parameters, launch files, lifecycle management, distributed security, or a full ecosystem of tools.

## Current Limits

- Discovery uses UDP multicast. Your network, OS, firewall, container runtime, or VPN must allow multicast traffic.
- The default multicast TTL is one hop, so discovery is intended for the local LAN, not routed networks.
- Remote node filtering currently assumes a `/24` subnet through a hard-coded `255.255.255.0` mask.
- All traffic (pub/sub + services) uses a single ephemeral TCP port per node, which can be inconvenient on locked-down firewalls.
- Communication is not encrypted or authenticated. Use pyzlc on trusted networks only.
- Integration tests for real networking are opt-in and currently represented by a skipped placeholder.

## Installation

```bash
pip install pyzlc
```

For local development:

```bash
git clone <your-fork-or-repo-url>
cd pyzlc
pip install -e ".[test]"
.venv/bin/python -m pytest
```

If you are not using the checked-in virtual environment, run `python -m pytest` with the Python environment where you installed the test extra.

## Quick Start: Pub/Sub

Open two terminals on the same machine. Save the first script as `publisher.py`:

```python
import pyzlc

pyzlc.init("PublisherNode", "127.0.0.1")
pub = pyzlc.Publisher("chat")

count = 0
while True:
    pub.publish({"user": "publisher", "text": f"hello {count}"})
    pyzlc.info("published message %d", count)
    count += 1
    pyzlc.sleep(1)
```

Save the second script as `subscriber.py`:

```python
import pyzlc


def on_chat(message):
    pyzlc.info("received from %s: %s", message["user"], message["text"])


pyzlc.init("SubscriberNode", "127.0.0.1")
pyzlc.register_subscriber_handler("chat", on_chat)
pyzlc.spin()
```

Run them:

```bash
python publisher.py
python subscriber.py
```

## Quick Start: Services

Services provide request/response calls. Save this as `service_server.py`:

```python
import pyzlc


def add_ints(request):
    return {"sum": request["a"] + request["b"]}


pyzlc.init("ServiceNode", "127.0.0.1")
pyzlc.register_service_handler("add_ints", add_ints)
pyzlc.spin()
```

Save this as `service_client.py`:

```python
import pyzlc

pyzlc.init("ClientNode", "127.0.0.1")

if not pyzlc.wait_for_service("add_ints", timeout=5.0):
    raise RuntimeError("service was not discovered")

response = pyzlc.call("add_ints", {"a": 10, "b": 20})
print(response["sum"])
```

Run the server first, then the client:

```bash
python service_server.py
python service_client.py
```

## Cross-Host Setup

To run across two machines, use each machine's real LAN IP address instead of `127.0.0.1`.

Example:

```python
# Host A, for example 192.168.1.20
pyzlc.init("PublisherNode", "192.168.1.20")

# Host B, for example 192.168.1.30
pyzlc.init("SubscriberNode", "192.168.1.30")
```

Checklist for cross-host discovery:

- Put both hosts on the same multicast-capable LAN.
- Use the IP address for the network interface that should send and receive pyzlc traffic.
- Allow UDP multicast on port `7720`, or pass a shared `group_port` to `pyzlc.init(...)`.
- Allow inbound TCP connections to the ephemeral ports advertised by publishers and services.
- Keep the same `group_name`, multicast `group`, and `group_port` on nodes that should discover each other.
- Avoid `127.0.0.1` for cross-host runs. It only refers to the current machine.

Custom group example:

```python
pyzlc.init(
    node_name="RobotNode",
    node_ip="192.168.1.20",
    group_name="robot_lab",
    group="224.0.0.1",
    group_port=7720,
)
```

## API Summary

- `pyzlc.init(node_name, node_ip, group_name=..., group=..., group_port=...)`: starts one local node and begins multicast discovery.
- `pyzlc.Publisher(topic_name)`: advertises a topic and publishes msgpack-serializable Python values.
- `pyzlc.register_subscriber_handler(topic_name, callback)`: subscribes to matching publishers and calls `callback(message)`.
- `pyzlc.register_service_handler(service_name, callback)`: registers a request/response service.
- `pyzlc.wait_for_service(service_name, timeout=5.0)`: waits for a service to appear in discovered node metadata.
- `pyzlc.call(service_name, request, timeout=2.0)`: synchronously calls a service and returns its response, or `None` on failure.
- `pyzlc.spin()`: blocks the main thread while background communication continues.
- `pyzlc.shutdown()`: stops local pyzlc nodes and background workers.

Messages, requests, and responses are serialized with `msgpack`. Dictionaries, lists, strings, numbers, booleans, and `None` are the safest choices.

## Architecture

`pyzlc` uses a small hybrid transport:

- UDP multicast sends heartbeat packets that advertise node identity, metadata version, service port, and group name.
- When a node sees new or changed metadata, it calls the remote built-in `get_node_info` service to fetch topics and services.
- asyncio TCP carries cross-host topic data and service calls on a single port per node.
- Unix domain sockets (IPC) are used automatically for same-host topic subscriptions for lower local overhead.
- A background asyncio loop and daemon worker pool let synchronous scripts publish, subscribe, call services, and block in `spin()`.

## Troubleshooting

No nodes are discovered:

- Confirm every node uses the correct LAN IP, not `127.0.0.1`.
- Check that both machines are in the same `/24` subnet, for example `192.168.1.x`.
- Confirm multicast is enabled on the network. Some Wi-Fi, VPN, Docker, WSL, and cloud networks block it.
- Allow UDP traffic on the configured `group_port`, default `7720`.
- Use the same `group_name`, multicast `group`, and `group_port` on all related nodes.

Service calls time out:

- Call `pyzlc.wait_for_service(...)` before `pyzlc.call(...)`.
- Check that the service process is still running and has called `pyzlc.spin()`.
- Allow inbound TCP connections to the service host.
- Increase the call timeout if the handler legitimately takes longer than the default `2.0` seconds.

Duplicate service errors:

- Service names must be unique within the discovered group.
- Use different service names or separate groups for independent systems.

Subscribers do not receive messages:

- Start the subscriber before or shortly after the publisher, then leave both processes running.
- Check that topic names match exactly.
- For cross-host traffic, confirm the publisher's advertised TCP port is reachable from the subscriber host.

## Development And Testing

Install test dependencies:

```bash
pip install -e ".[test]"
```

Run the default unit suite:

```bash
python -m pytest
```

The default pytest configuration excludes integration and benchmark tests:

```bash
python -m pytest -m "integration"
python -m pytest -m "benchmark" --benchmark-only
```

Benchmarks require the benchmark extra:

```bash
pip install -e ".[test,benchmark]"
```

Coverage report:

```bash
python -m pytest --cov=pyzlc --cov-report=term-missing
```

PyPI publishing is configured through GitHub Actions and runs when a `v*` tag is pushed.

## Improvement Backlog

These are the highest-value next improvements for making pyzlc more reliable and easier to adopt:

1. Cross-host reliability: make subnet filtering configurable instead of hard-coded `/24`, expose or document multicast TTL/interface selection, and support fixed or ranged TCP ports for firewall-friendly deployments.
2. Real integration coverage: replace the skipped network placeholder with localhost pub/sub, service call, discovery, shutdown/restart, and multi-group tests.
3. Subscriber behavior: use `RCVHWM` for subscriber receive buffering, and define how multiple callbacks on the same topic should behave.
4. Shutdown/resource management: track publisher sockets so `shutdown()` closes them, cancel and await background tasks cleanly, and ensure the shared TCP server is properly shut down.
5. Public API polish: broaden message typing to match documented msgpack support, improve `wait_for_service_async` behavior with user event loops, and avoid masking coroutine errors with `task.__name__`.
6. Packaging quality: add richer PyPI classifiers, project URLs, ruff configuration in `pyproject.toml`, and CI for tests across supported Python versions.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
