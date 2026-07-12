"""Base domain exception hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final


@dataclass(frozen=True)
class MangoError(Exception):
    """Base for all domain and application-level errors."""

    message: str
    code: str = "domain_error"

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


@final
class ValidationError(MangoError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="validation_error")


@final
class NotFoundError(MangoError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="not_found")


@final
class ConflictError(MangoError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="conflict")


@final
class UnauthorizedError(MangoError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="unauthorized")


@final
class ForbiddenError(MangoError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="forbidden")


@final
class InternalError(MangoError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="internal_error")
