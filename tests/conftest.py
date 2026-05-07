import itertools
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional
from uuid import uuid4

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
        return f"{prefix}_{uuid4().hex}_{next(counter)}"

    return factory


@pytest.fixture
def unique_group_port():
    counter = itertools.count(17720)

    def factory():
        return next(counter)

    return factory


@pytest.fixture
def eventually():
    def assert_eventually(
        predicate: Callable[[], bool],
        timeout: float = 3.0,
        interval: float = 0.05,
        message: str = "condition was not met before timeout",
    ) -> None:
        deadline = time.monotonic() + timeout
        last_error: Optional[AssertionError] = None
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except AssertionError as exc:
                last_error = exc
            time.sleep(interval)
        if last_error is not None:
            raise AssertionError(message) from last_error
        raise AssertionError(message)

    return assert_eventually


@pytest.fixture
def python_snippet_runner():
    processes = []

    def make_env(extra_env=None):
        env = os.environ.copy()
        pythonpath_parts = [str(SRC)]
        if env.get("PYTHONPATH"):
            pythonpath_parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
        if extra_env:
            env.update(extra_env)
        return env

    def run(code: str, timeout: float = 10.0, extra_env=None):
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=make_env(extra_env),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def start(code: str, extra_env=None):
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=make_env(extra_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(process)
        return process

    yield SimpleNamespace(run=run, start=start, make_env=make_env)

    for process in processes:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


@pytest.fixture
def require_local_zmq_network(
    python_snippet_runner,
    unique_group_name,
    unique_group_port,
):
    group_name = unique_group_name("network_probe")
    group_port = unique_group_port()
    probe = f"""
import pyzlc

pyzlc.init(
    "NetworkProbe",
    "127.0.0.1",
    group_name={group_name!r},
    group_port={group_port},
)
pyzlc.shutdown()
"""
    result = python_snippet_runner.run(probe, timeout=5.0)
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return
    if "Operation not permitted" in output:
        pytest.skip(f"local ZeroMQ/multicast is not permitted: {output.strip()}")
    pytest.fail(
        "local ZeroMQ/multicast probe failed\n"
        f"returncode: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
