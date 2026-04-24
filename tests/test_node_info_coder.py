import random
import string
from typing import Optional

import pytest

from pyzlc.utils.msg import create_hash_identifier
from pyzlc.utils.node_info import NodeInfo, decode_node_info, encode_node_info


def generate_random_string(length: int) -> str:
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(length))


def generate_random_ip() -> str:
    return (
        f"{random.randint(1, 255)}.{random.randint(0, 255)}."
        f"{random.randint(0, 255)}.{random.randint(1, 254)}"
    )


def generate_random_node_info(
    num_topics: Optional[int] = None,
    num_services: Optional[int] = None,
) -> NodeInfo:
    if num_topics is None:
        num_topics = random.randint(1, 10)
    if num_services is None:
        num_services = random.randint(1, 10)

    node_ip = generate_random_ip()
    return {
        "nodeID": create_hash_identifier(),
        "infoID": random.randint(0, 0xFFFFFFFF),
        "name": f"node_{generate_random_string(8)}",
        "ip": node_ip,
        "topics": [
            {"name": f"topic_{i}", "ip": node_ip, "port": random.randint(1024, 65535)}
            for i in range(num_topics)
        ],
        "services": [
            {"name": f"svc_{i}", "ip": node_ip, "port": random.randint(1024, 65535)}
            for i in range(num_services)
        ],
    }


@pytest.mark.unit
def test_encode_decode_identity():
    for _ in range(100):
        original_data = generate_random_node_info()

        encoded = encode_node_info(original_data)
        decoded = decode_node_info(encoded)

        assert decoded == original_data


@pytest.mark.unit
@pytest.mark.parametrize("list_size", [0, 1, 50])
def test_variable_list_sizes(list_size):
    data = generate_random_node_info()
    data["topics"] = [
        {"name": "t", "ip": "1.1.1.1", "port": 80} for _ in range(list_size)
    ]

    encoded = encode_node_info(data)
    decoded = decode_node_info(encoded)

    assert len(decoded["topics"]) == list_size


@pytest.mark.unit
def test_decode_rejects_truncated_data():
    with pytest.raises(Exception):
        decode_node_info(b"short")


@pytest.mark.benchmark
def test_benchmark_encode(benchmark):
    data = generate_random_node_info(10, 10)
    benchmark(encode_node_info, data)


@pytest.mark.benchmark
def test_benchmark_decode(benchmark):
    data = generate_random_node_info(10, 10)
    encoded_bytes = encode_node_info(data)
    benchmark(decode_node_info, encoded_bytes)
