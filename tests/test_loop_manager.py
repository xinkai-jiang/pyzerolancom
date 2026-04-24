import pytest

from pyzlc.nodes.loop_manager import DaemonThreadPoolExecutor


@pytest.mark.unit
def test_daemon_thread_pool_executor_returns_results():
    executor = DaemonThreadPoolExecutor(max_workers=1)
    future = executor.submit(lambda x, y: x + y, 2, 3)

    assert future.result(timeout=1) == 5
    executor.shutdown(wait=True)


@pytest.mark.unit
def test_daemon_thread_pool_executor_rejects_after_shutdown():
    executor = DaemonThreadPoolExecutor(max_workers=1)

    executor.shutdown(wait=True)

    with pytest.raises(RuntimeError):
        executor.submit(lambda: None)
