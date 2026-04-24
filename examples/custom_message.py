from typing import TypedDict, List

import pyzlc


class CustomMessage(TypedDict):
    """A custom message structure."""

    count: int
    name: str
    data: List[float]


def message_callback(msg: CustomMessage):
    """Callback function to handle received custom messages."""
    pyzlc.info("========== Received Custom Message ==========")
    pyzlc.info("Topic received message %s", msg["count"])
    pyzlc.info("Name: %s", msg["name"])
    pyzlc.info("Values: %s", msg["data"])


if __name__ == "__main__":
    pyzlc.init("CustomMessageNode", "127.0.0.1", log_level=pyzlc.LogLevel.DEBUG)
    pyzlc.register_subscriber_handler("CustomMessage", message_callback)
    pub = pyzlc.Publisher("CustomMessage")
    count = 0
    while True:
        pub.publish(CustomMessage(count=count, name="example", data=[1.0, 2.0, 3.0]))
        pyzlc.info(f"Published custom message with count: {count}")
        count += 1
        pyzlc.sleep(0.5)
