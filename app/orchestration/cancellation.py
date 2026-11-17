"""Race real asynchronous work against cooperative Stop and a bounded deadline."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


async def run_cancellable(
    work: Awaitable[T], cancelled: asyncio.Event, timeout: float
) -> T:
    """Close the underlying coroutine on Stop/timeout; completed work is never substituted."""
    task = asyncio.ensure_future(work)
    stopping = asyncio.create_task(cancelled.wait())
    try:
        done, _ = await asyncio.wait(
            {task, stopping}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if stopping in done or cancelled.is_set():
            raise asyncio.CancelledError()
        if task not in done:
            raise TimeoutError("Execution deadline reached")
        return await task
    finally:
        if not task.done():
            task.cancel()
        stopping.cancel()
        await asyncio.gather(task, stopping, return_exceptions=True)
