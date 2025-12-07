import pyzerolancom
from pyzerolancom import Publisher
from pyzerolancom.utils.log import logger

def create_topic_callback(topic_name: str):
    """Create a topic callback that prints the received message."""
    def topic_callback(msg: str):
        logger.info("Topic %s received message: %s", topic_name, msg)
    return topic_callback



if __name__ == "__main__":
    node = pyzerolancom.init_node("TopicExampleNode", "127.0.0.1")
    publisher = Publisher("example_topic")
    node.create_subscriber("example_topic", create_topic_callback("example_topic"))
    while node.running:
        publisher.publish("Hello, PyZeroLanCom!")
        logger.info("Published message to topic 'example_topic'")
        node.sleep(1)
