import pytest

from pyzlc.utils.msg import (
    HeartbeatMessage,
    ResponseStatus,
    create_hash_identifier,
    decode_heartbeat_message,
    is_in_same_subnet,
)


@pytest.mark.unit
def test_create_hash_identifier_is_uuid_sized_string():
    identifier = create_hash_identifier()

    assert isinstance(identifier, str)
    assert len(identifier) == 36


@pytest.mark.unit
def test_heartbeat_message_round_trip():
    original = HeartbeatMessage(
        zlc_version=(2, 2, 0),
        node_id=create_hash_identifier(),
        info_id=3,
        service_port=45678,
        group_name="group_a",
    )

    decoded = decode_heartbeat_message(original.to_bytes())

    assert decoded is not None
    assert decoded.zlc_version == original.zlc_version
    assert decoded.node_id == original.node_id
    assert decoded.info_id == original.info_id
    assert decoded.service_port == original.service_port
    assert decoded.group_name == original.group_name


@pytest.mark.unit
def test_decode_heartbeat_rejects_short_message():
    assert decode_heartbeat_message(b"short") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("ip1", "ip2", "expected"),
    [
        ("192.168.1.10", "192.168.1.20", True),
        ("192.168.1.10", "192.168.2.20", False),
        ("bad-ip", "192.168.1.20", False),
    ],
)
def test_is_in_same_subnet(ip1, ip2, expected):
    assert is_in_same_subnet(ip1, ip2) is expected


@pytest.mark.unit
def test_response_status_success_is_not_error():
    assert ResponseStatus.is_error(ResponseStatus.SUCCESS) is False
    assert ResponseStatus.is_error(ResponseStatus.NOSERVICE) is True
