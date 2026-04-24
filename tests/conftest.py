import itertools
import random
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def deterministic_random_seed():
    random.seed(0)


@pytest.fixture(autouse=True)
def cleanup_pyzlc():
    yield
    try:
        import pyzlc

        pyzlc.shutdown()
    except Exception:
        pass


@pytest.fixture
def unique_group_name():
    counter = itertools.count()

    def factory(prefix="test_group"):
        return f"{prefix}_{next(counter)}"

    return factory


@pytest.fixture
def unique_group_port():
    counter = itertools.count(17720)

    def factory():
        return next(counter)

    return factory
