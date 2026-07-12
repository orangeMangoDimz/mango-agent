"""Unit of Work port for atomic transactions across repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, final

__all__ = ["UnitOfWork", "UnitOfWorkFactory"]


class UnitOfWork(ABC):
    """Abstract unit of work with explicit transaction boundaries.

    Repository attributes are typed as ``Any`` so the abstract port can be
    shared across modules without importing every concrete repository type.
    Application code asserts the expected repositories after ``begin()``.
    """

    users: Any = None
    provider_identities: Any = None
    projects: Any = None
    tasks: Any = None
    attachments: Any = None
    idempotency: Any = None

    @abstractmethod
    async def begin(self) -> None:
        """Start a transaction."""

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""


type UnitOfWorkFactory = Callable[[], UnitOfWork]


@final
class UnitOfWorkFactoryError(Exception):
    """Raised when a unit of work factory cannot create a unit of work."""
