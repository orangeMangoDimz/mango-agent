"""Unit of Work port for atomic transactions across repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod

__all__ = ["UnitOfWork"]


class UnitOfWork(ABC):
    """Abstract unit of work with explicit transaction boundaries."""

    @abstractmethod
    async def begin(self) -> None:
        """Start a transaction."""

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""
