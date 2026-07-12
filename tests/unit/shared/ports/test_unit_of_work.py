"""Unit tests for the UnitOfWork port."""

from __future__ import annotations

from types import TracebackType

from mango_agent.shared.ports.unit_of_work import UnitOfWork


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.begun = False
        self.committed = False
        self.rolled_back = False

    async def begin(self) -> None:
        self.begun = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> FakeUnitOfWork:
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is None:
            await self.commit()
        else:
            await self.rollback()


async def test_fake_unit_of_work_lifecycle() -> None:
    uow = FakeUnitOfWork()
    await uow.begin()
    await uow.commit()
    await uow.rollback()
    assert uow.begun
    assert uow.committed
    assert uow.rolled_back
