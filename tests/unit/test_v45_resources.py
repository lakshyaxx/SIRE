"""Real OS-lock exclusivity, bounded waiting, queue priority and cancellation cleanup."""

import asyncio
import pytest
from app.core.errors import SireError
from app.providers.resources import ResourceScheduler


def test_independent_schedulers_respect_same_os_lock_and_timeout(tmp_path):
    first = ResourceScheduler(tmp_path / "test-only.lock", wait_seconds=0.1)
    second = ResourceScheduler(tmp_path / "test-only.lock", wait_seconds=0.05)
    with first.lease("test-only-heavy"):
        with pytest.raises(SireError) as failure:
            with second.lease("test-only-other"):
                pytest.fail("Two schedulers acquired the same heavy slot")
        assert failure.value.code == "model_queue_timeout"
        assert not second.snapshot()["active"] and not second.snapshot()["waiting"]
    with second.lease("test-only-after-release"):
        assert len(second.snapshot()["active"]) == 1
    assert not second.snapshot()["active"]


def test_foreground_priority_and_cancelled_waiter_do_not_leak_slot(tmp_path):
    scheduler = ResourceScheduler(
        tmp_path / "test-only.lock", queue_limit=3, wait_seconds=1
    )

    async def run():
        order = []

        async def work(name, priority):
            async with scheduler.async_lease(name, priority=priority):
                order.append(name)

        with scheduler.lease("test-only-initial"):
            deep = asyncio.create_task(work("test-only-deep", 10))
            fast = asyncio.create_task(work("test-only-chat", 0))
            abandoned = asyncio.create_task(work("test-only-cancelled", -1))
            await asyncio.sleep(0)
            abandoned.cancel()
            with pytest.raises(asyncio.CancelledError):
                await abandoned
            assert len(scheduler.snapshot()["waiting"]) == 2
        await asyncio.gather(deep, fast)
        assert order == ["test-only-chat", "test-only-deep"]
        assert (
            not scheduler.snapshot()["waiting"] and not scheduler.snapshot()["active"]
        )
        assert all(row["total_seconds"] >= 0 for row in scheduler.snapshot()["recent"])

    asyncio.run(run())


def test_queue_capacity_and_cancel_signal_are_explicit(tmp_path):
    scheduler = ResourceScheduler(
        tmp_path / "test-only.lock", queue_limit=1, wait_seconds=1
    )

    async def run():
        flag = asyncio.Event()

        async def work():
            async with scheduler.async_lease("test-only-waiter", cancelled=flag):
                pytest.fail("Cancelled waiter acquired slot")

        with scheduler.lease("test-only-active"):
            task = asyncio.create_task(work())
            await asyncio.sleep(0)
            with pytest.raises(SireError) as full:
                async with scheduler.async_lease("test-only-overflow"):
                    pass
            assert full.value.code == "model_queue_full"
            flag.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert (
            not scheduler.snapshot()["waiting"] and not scheduler.snapshot()["active"]
        )

    asyncio.run(run())
