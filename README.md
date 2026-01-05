# pyzlc

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-green)
[![PyPI version](https://badge.fury.io/py/pyzlc.svg)](https://badge.fury.io/py/pyzlc)

**pyzlc** is a lightweight, cross-environment communication framework designed for Python applications running on Local Area Networks (LAN). Built on top of [ZeroMQ](https://zguide.zeromq.org/), it features automatic node discovery, enabling nodes to dynamically find and connect to sockets from other peers without manual configuration.

**pyzlc** eliminates the need for heavyweight frameworks like [ROS](https://www.ros.org/) or [ROS2](https://docs.ros.org/en/foxy/index.html) when you simply need to establish quick, reliable communication—whether on the same host or distributed across different machines—while maintaining a minimal dependency footprint.

## 🚀 Key Features
Zero-Config Discovery: Nodes automatically discover and update each other on the LAN using multicast heartbeats—no master node or manual IP configuration required.

ROS-like API: Designed with a familiar workflow for ROS users. simply initialize a node, register your publishers/subscribers, and start communicating with minimal boilerplate.

Automatic Serialization: Native support for dictionaries, lists, and primitives via msgpack, removing the need to manually define encoders or decoders. Future support is planned for Protobuf and Flatbuffers.

Async-First Architecture: Built on top of Python’s asyncio and ZeroMQ for high-performance, non-blocking asynchronous applications.

Rich Logging: Integrated, color-coded logging system to simplify debugging and status monitoring.

## 📦 Installation

```bash
pip install pyzlc
```

## ⚡ Quick Start
1. Initialization
Every script starts by initializing the singleton node.

```python
import pyzlc

# Initialize the node with a unique name and your local IP
pyzlc.init(node_name="MyNode", node_ip="127.0.0.1")
```

2. Pub/Sub Pattern
Publish messages to a specific topic and subscribe to updates.

Publisher:

```python
import pyzlc
import time

pyzlc.init("PublisherNode", "127.0.0.1")
pub = pyzlc.Publisher("chat_room")

while True:
    # You can send strings, dicts, or lists directly!
    pub.publish({"user": "admin", "text": "Hello World"})
    pyzlc.info("Message published")
    pyzlc.sleep(1)
```
Subscriber:

```python
import pyzlc

def on_chat_message(msg):
    # msg is automatically unpacked into a python dict
    pyzlc.info(f"Received from {msg['user']}: {msg['text']}")

if __name__ == "__main__":
    pyzlc.init("SubscriberNode", "127.0.0.1")
    
    # Register a callback for the topic
    pyzlc.register_subscriber_handler("chat_room", on_chat_message)
    
    # Keep the node running
    pyzlc.spin()
```

3. Service (RPC) Pattern
Perform Request/Response communication between nodes.

Server (Service Provider):

```python
import pyzlc

def add_two_ints(request):
    """Takes a dict, returns the sum."""
    result = request['a'] + request['b']
    pyzlc.info(f"Calculated: {result}")
    return {"sum": result}

if __name__ == "__main__":
    pyzlc.init("ServerNode", "127.0.0.1")
    
    # Register the service
    pyzlc.register_service_handler("add_ints", add_two_ints)
    
    pyzlc.spin()
```

Client (Caller):

```python
import pyzlc

pyzlc.init("ClientNode", "127.0.0.1")

# Wait for service to be discovered on the network
pyzlc.wait_for_service("add_ints")

# Call the service synchronously
response = pyzlc.call("add_ints", {"a": 10, "b": 20})
print(f"Result: {response['sum']}") # Output: 30
```

## 🛠 Advanced Usage
Data Streaming
For high-frequency data (e.g., sensor readings), use the Streamer class to publish at a fixed FPS.

```python
from pyzlc.sockets.publisher import Streamer
import random

def get_sensor_data():
    return {"temp": 20 + random.random(), "timestamp": time.time()}

# Create a streamer that calls get_sensor_data() 30 times per second
streamer = Streamer("sensor_stream", get_sensor_data, fps=30, start_streaming=True)

pyzlc.spin()
```

Custom Message Structures
Because pyzlc uses msgpack, you can use Python TypedDict to define schemas, but you don't need special compilation steps.

```python
from typing import TypedDict, List

class RobotState(TypedDict):
    id: int
    joints: List[float]
    active: bool

# The library handles serialization automatically
msg: RobotState = {"id": 1, "joints": [0.1, 1.2, -0.5], "active": True}
publisher.publish(msg)
```

## 🧩 Architecture
pyzlc uses a hybrid architecture to ensure reliability and speed:

- UDP Multicast: Used for node presence (Heartbeats) and discovery.
- TCP (ZeroMQ): Used for actual data transport (PUB/SUB and REQ/REP) to ensure reliable delivery.
- Loop Manager: A dedicated thread pool handles the asyncio event loop, allowing you to run blocking code alongside async communication if needed.

## 📋 Requirements
Python 3.8+

pyzmq

msgpack

colorama

## License
This project is licensed under the Apache License 2.0 - see the LICENSE file for details.