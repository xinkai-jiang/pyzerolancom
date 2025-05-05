import abc
import asyncio
import concurrent.futures
import time
import traceback
from asyncio import AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, Optional, Union

from ..utils.log import logger


class LanComLoopManager(abc.ABC):

    def __init__(self, max_workers: int = 3):
        self._loop: Optional[AbstractEventLoop] = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running: bool = False


    def spin_task(self) -> None:
        logger.info("Starting spin task")
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.running = True
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.stop_node()
        except Exception as e:
            logger.error(f"Unexpected error in thread_task: {e}")
            traceback.print_exc()
            self.stop_node()
        finally:
            self.loop.close()
            logger.info("Spin task has been stopped")
            self.running = False
            self._executor.shutdown(wait=False)
            logger.info("Thread pool has been stopped")

    def spin(self) -> None:
        while self.running:
            time.sleep(0.05)

    def stop_node(self):
        self.running = False
        try:
            if self.loop is not None:
                self.loop.call_soon_threadsafe(self.loop.stop)
        except RuntimeError as e:
            logger.error(f"One error occurred when stop server: {e}")
        assert self._executor is not None
        self._executor.shutdown(wait=False)

    async def run_in_executor(
        self,
        func: Union[Coroutine[Any, Any, Any], Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self._loop is None:
            raise RuntimeError("Event loop is not initialized")
        return await self.loop.run_in_executor(self._executor, func, *args, **kwargs)

    def submit_loop_task(
        self,
        task: Coroutine,
        block: bool = False,
    ) -> Union[concurrent.futures.Future, Any]:
        if not self._loop:
            raise RuntimeError("The event loop is not running")
        future = asyncio.run_coroutine_threadsafe(
            task, self._loop
        )
        if block:
            return future.result()
        return future
