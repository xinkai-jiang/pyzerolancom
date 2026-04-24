from __future__ import annotations

import asyncio
import concurrent.futures
import time
import traceback
from asyncio import AbstractEventLoop
import threading
import queue
import uuid
from concurrent.futures import Future
from typing import Any, Coroutine, Optional, Callable, TypeVar, Tuple, Dict

from ..utils.log import _logger

TaskReturnT = TypeVar("TaskReturnT")
TaskPayload = Tuple[Future, Callable[..., Any], Tuple[Any, ...], Dict[str, Any]]


class DaemonThreadPoolExecutor:
    def __init__(self, max_workers=5):
        """
        Initialize the executor with a maximum number of worker threads.
        All threads created will be set as daemon threads.
        """
        self._max_workers = max_workers
        self._work_queue: queue.Queue[TaskPayload] = queue.Queue()
        self._threads = set()
        self._shutdown = False
        self._lock = threading.Lock()

    def submit(self, fn, *args, **kwargs):
        """
        Submit a callable to be executed and return a Future object.
        """
        with self._lock:
            if self._shutdown:
                raise RuntimeError("Cannot submit new tasks after shutdown.")

            # Create a Future object to track task status and result
            future = Future()
            # Wrap the function and future into a WorkItem
            work_item = (future, fn, args, kwargs)
            
            self._work_queue.put(work_item)

            # Lazy-start threads until max_workers is reached
            if len(self._threads) < self._max_workers:
                self._spawn_worker()

            return future

    def _spawn_worker(self):
        """Internal method to spawn a new daemon thread."""
        thread_name = f"DaemonWorker-{uuid.uuid4().hex[:6]}"
        t = threading.Thread(target=self._worker, name=thread_name)
        t.daemon = True # Ensure the thread does not block program exit
        self._threads.add(t)
        t.start()

    def _worker(self):
        """The main loop for worker threads."""
        while True:
            try:
                # Poll the queue with a timeout to allow checking shutdown state
                work_item = self._work_queue.get(timeout=0.5)
            except queue.Empty:
                if self._shutdown:
                    break
                continue

            future, fn, args, kwargs = work_item

            # Only execute if the future hasn't been cancelled
            if not future.set_running_or_notify_cancel():
                self._work_queue.task_done()
                continue

            try:
                # Execute the task and capture the result
                result = fn(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                # Capture exceptions and set them on the future
                future.set_exception(e)
            finally:
                self._work_queue.task_done()

        # Self-cleanup upon thread exit
        current_t = threading.current_thread()
        if current_t in self._threads:
            self._threads.remove(current_t)

    def shutdown(self, wait=True):
        """
        Signal the executor to stop. 
        If wait is True, block until all pending tasks are finished.
        """
        with self._lock:
            self._shutdown = True
        
        if wait:
            self._work_queue.join()


class TaskLoopManager:
    """Manages the event loop and thread pool for asynchronous tasks."""

    instance: Optional[TaskLoopManager] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> TaskLoopManager:
        """Create or return the singleton loop manager instance."""
        if cls.instance is None:
            with cls._instance_lock:
                if cls.instance is None:
                    cls.instance = super().__new__(cls)
        return cls.instance

    @classmethod
    def get_instance(cls) -> TaskLoopManager:
        """Get the singleton instance of TaskLoopManager."""
        return cls()

    def __init__(self, max_workers: int = 3):
        """Initialize the TaskLoopManager with a thread pool executor.

        Args:
            max_workers (int, optional): The maximum number of worker threads. Defaults to 3.
        """
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._loop: Optional[AbstractEventLoop] = None
        self._running: bool = False
        self._stopped_event = threading.Event()
        self._stop_lock = threading.Lock()
        self._executor = DaemonThreadPoolExecutor(max_workers=max_workers)
        self._spin_thread = threading.Thread(
            target=self.spin_task, name="LanComSpinTask", daemon=True
        )
        self._spin_thread.start()
        while self._loop is None:
            time.sleep(0.01)

    def spin_task(self) -> None:
        """Start the event loop and run it forever."""
        _logger.debug("Starting spin task")
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            self._loop.run_forever()
        except Exception as e:
            _logger.error("Unexpected error in thread_task: %s", e)
            traceback.print_exc()
            raise e
        finally:
            _logger.debug("Shutting down spin task")
            self._running = False
            if self._loop is not None:
                self._loop.close()
            self._stopped_event.set()
            _logger.debug("Spin task has been stopped")

    def spin(self) -> None:
        """Start the spin task in a separate thread."""
        try:
            self._stopped_event.wait()
        except KeyboardInterrupt:
            self.stop()
            raise KeyboardInterrupt

    def stop(self):
        """Stop the event loop and shut down the thread pool executor safely."""
        with self._stop_lock:
            if self._stopped_event.is_set():
                return

            self._running = False
            try:
                if self._loop is None:
                    raise RuntimeError("Event loop is not initialized")
                # When loop exits run_forever(), all remaining tasks are still pending.
                for task in asyncio.all_tasks(self._loop):
                    task.cancel()
                if self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
                _logger.debug("Event loop stop signal sent")
            except RuntimeError as e:
                _logger.error("One error occurred when stop loop manager: %s", e)
                traceback.print_exc()

            self._stopped_event.wait()
            assert self._executor is not None
            self._executor.shutdown(wait=True)
            with TaskLoopManager._instance_lock:
                TaskLoopManager.instance = None
            _logger.debug("Thread pool executor has been shut down")
            _logger.debug("TaskLoopManager has been stopped")

    async def run_in_executor(
        self, func: Callable[..., TaskReturnT], *args: Any
    ) -> TaskReturnT:
        """
        Run a synchronous function in the executor.

        Args:
            func: The callable to run.
            *args: Positional arguments for the function.

        Returns:
            The result of the function (can be a single value or a tuple).
        """
        if self._loop is None:
            raise RuntimeError("Event loop is not initialized")

        # In Python 3.9, positional args are natively supported
        # and highly efficient in run_in_executor.
        return await self._loop.run_in_executor(self._executor, func, *args)

    def submit_loop_task(
        self,
        task: Coroutine[Any, Any, TaskReturnT],
    ) -> concurrent.futures.Future:
        """Submit a coroutine to the background event loop.

        Args:
            task (Coroutine[Any, Any, TaskReturnT]): The coroutine to schedule.

        Raises:
            RuntimeError: If the event loop has not been initialized.

        Returns:
            concurrent.futures.Future: A thread-safe future for the coroutine result.
        """
        if not self._loop:
            raise RuntimeError("The event loop is not running")

        async def wrapper():
            try:
                result = await task
            except Exception as e:
                _logger.error("Error in submitted task: %s %s", task.__name__, e)
                traceback.print_exc()
                raise e
            return result

        return asyncio.run_coroutine_threadsafe(wrapper(), self._loop)

    def submit_loop_task_and_wait(
        self, task: Coroutine[Any, Any, TaskReturnT]
    ) -> TaskReturnT:
        """Submit a coroutine to the event loop and block for its result.

        Args:
            task (Coroutine[Any, Any, TaskReturnT]): The coroutine to schedule.

        Raises:
            RuntimeError: If the event loop has not been initialized.

        Returns:
            TaskReturnT: The value returned by the coroutine.
        """
        if not self._loop:
            raise RuntimeError("The event loop is not running")
        future = asyncio.run_coroutine_threadsafe(task, self._loop)
        return future.result()

    def submit_thread_pool_task(
        self, func: Callable[..., TaskReturnT], *args: Any
    ) -> Future:
        """Submit a synchronous callable to the internal thread pool."""
        return self._executor.submit(func, *args)
