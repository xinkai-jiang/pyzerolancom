import pytest


pytestmark = [pytest.mark.integration, pytest.mark.network]


def test_network_integration_placeholder():
    pytest.skip("Real ZeroMQ/multicast integration tests are opt-in and not implemented yet.")
