import json
import subprocess
import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.usage]

RESULT_PREFIX = "PYZLC_TEST_RESULT:"

SUBSCRIBER_EXAMPLE_SNIPPET = """
import json
import os
import sys
import time

import pyzlc

group_name = os.environ["PYZLC_TEST_GROUP_NAME"]
group_port = int(os.environ["PYZLC_TEST_GROUP_PORT"])
received = []


def message_callback(msg):
    received.append(msg)


pyzlc.init("Subscriber", "127.0.0.1", group_name=group_name, group_port=group_port)
pyzlc.register_subscriber_handler("GreetingTopic", message_callback)

deadline = time.monotonic() + 8.0
while time.monotonic() < deadline and not received:
    time.sleep(0.05)

print("PYZLC_TEST_RESULT:" + json.dumps({"received": received}), flush=True)
pyzlc.shutdown()
sys.exit(0 if received else 3)
"""

PUBLISHER_EXAMPLE_SNIPPET = """
import os
import time

import pyzlc

group_name = os.environ["PYZLC_TEST_GROUP_NAME"]
group_port = int(os.environ["PYZLC_TEST_GROUP_PORT"])

pyzlc.init("Publisher", "127.0.0.1", group_name=group_name, group_port=group_port)
pub = pyzlc.Publisher("GreetingTopic")

for count in range(25):
    pub.publish({"timestamp": time.monotonic(), "count": count})
    pyzlc.sleep(0.1)

pyzlc.shutdown()
"""


def _extract_result(stdout: str):
    for line in stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            return json.loads(line.removeprefix(RESULT_PREFIX))
    raise AssertionError(f"missing {RESULT_PREFIX!r} line in stdout:\n{stdout}")


def test_topic_example_flow_receives_same_process_message(
    require_local_zmq_network,
    unique_group_name,
    unique_group_port,
    eventually,
):
    import pyzlc

    group_name = unique_group_name("topic_example")
    group_port = unique_group_port()
    received = []

    def topic_callback(msg: str):
        received.append(msg)

    pyzlc.init(
        "TopicExampleNode",
        "127.0.0.1",
        group_name=group_name,
        group_port=group_port,
    )
    publisher = pyzlc.Publisher("example_topic", group_name=group_name)
    pyzlc.register_subscriber_handler(
        "example_topic",
        topic_callback,
        group_name=group_name,
    )

    def publish_until_received():
        publisher.publish("Hello, pyzlc!")
        return "Hello, pyzlc!" in received

    eventually(
        publish_until_received,
        timeout=4.0,
        interval=0.1,
        message="topic_example flow did not deliver the published message",
    )


def test_custom_message_example_preserves_typed_dict_payload(
    require_local_zmq_network,
    unique_group_name,
    unique_group_port,
    eventually,
):
    import pyzlc

    group_name = unique_group_name("custom_message")
    group_port = unique_group_port()
    received = []
    message = {"count": 7, "name": "example", "data": [1.0, 2.0, 3.0]}

    def message_callback(msg):
        received.append(msg)

    pyzlc.init(
        "CustomMessageNode",
        "127.0.0.1",
        group_name=group_name,
        group_port=group_port,
        log_level=pyzlc.LogLevel.DEBUG,
    )
    pyzlc.register_subscriber_handler(
        "CustomMessage",
        message_callback,
        group_name=group_name,
    )
    publisher = pyzlc.Publisher("CustomMessage", group_name=group_name)

    def publish_until_received():
        publisher.publish(message)
        return bool(received) and received[-1] == message

    eventually(
        publish_until_received,
        timeout=4.0,
        interval=0.1,
        message="custom_message flow did not round-trip the payload",
    )
    assert received[-1]["count"] == 7
    assert received[-1]["name"] == "example"
    assert received[-1]["data"] == [1.0, 2.0, 3.0]


def test_service_example_echoes_request(
    require_local_zmq_network,
    unique_group_name,
    unique_group_port,
):
    import pyzlc

    group_name = unique_group_name("service_example")
    group_port = unique_group_port()
    service_name = "echo_service"

    def service_callback(msg: str) -> str:
        return msg

    pyzlc.init(
        "ServiceNode",
        "127.0.0.1",
        group_name=group_name,
        group_port=group_port,
    )
    pyzlc.register_service_handler(
        service_name,
        service_callback,
        group_name=group_name,
    )

    assert pyzlc.wait_for_service(service_name, timeout=2.0, group_name=group_name)
    assert (
        pyzlc.call(
            service_name,
            "Hello, world!",
            timeout=2.0,
            group_name=group_name,
        )
        == "Hello, world!"
    )


def test_publisher_and_subscriber_examples_exchange_timestamp_message(
    require_local_zmq_network,
    python_snippet_runner,
    unique_group_name,
    unique_group_port,
):
    group_name = unique_group_name("publisher_subscriber_examples")
    group_port = unique_group_port()
    extra_env = {
        "PYZLC_TEST_GROUP_NAME": group_name,
        "PYZLC_TEST_GROUP_PORT": str(group_port),
    }

    subscriber = python_snippet_runner.start(
        SUBSCRIBER_EXAMPLE_SNIPPET,
        extra_env=extra_env,
    )
    time.sleep(0.5)
    publisher = python_snippet_runner.run(
        PUBLISHER_EXAMPLE_SNIPPET,
        timeout=8.0,
        extra_env=extra_env,
    )
    try:
        subscriber_stdout, subscriber_stderr = subscriber.communicate(timeout=10.0)
    except subprocess.TimeoutExpired as exc:
        subscriber.kill()
        subscriber_stdout, subscriber_stderr = subscriber.communicate()
        raise AssertionError(
            "subscriber example process timed out\n"
            f"publisher stdout:\n{publisher.stdout}\n"
            f"publisher stderr:\n{publisher.stderr}\n"
            f"subscriber stdout:\n{subscriber_stdout}\n"
            f"subscriber stderr:\n{subscriber_stderr}"
        ) from exc

    assert publisher.returncode == 0, (
        "publisher example process failed\n"
        f"stdout:\n{publisher.stdout}\n"
        f"stderr:\n{publisher.stderr}"
    )
    assert subscriber.returncode == 0, (
        "subscriber example process did not receive a message\n"
        f"stdout:\n{subscriber_stdout}\n"
        f"stderr:\n{subscriber_stderr}\n"
    )

    result = _extract_result(subscriber_stdout)
    messages = result["received"]
    assert messages
    assert isinstance(messages[0]["timestamp"], float)
    assert isinstance(messages[0]["count"], int)
