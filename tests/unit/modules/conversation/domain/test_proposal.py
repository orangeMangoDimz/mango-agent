from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mango_agent.modules.conversation.domain.proposal import PendingProposal
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, OperationId
from mango_agent.shared.domain.value_objects import Timestamp


def _future(seconds: int = 60) -> Timestamp:
    return Timestamp.from_datetime(datetime.now(tz=UTC) + timedelta(seconds=seconds))


def test_proposal_create() -> None:
    operation_id = OperationId.generate()
    proposal = PendingProposal.create(operation_id, "Create task Buy mangoes", expires_at=_future())
    assert proposal.operation_id == operation_id
    assert proposal.version == 1
    assert proposal.consumed is False


def test_proposal_empty_content_raises() -> None:
    with pytest.raises(ValidationError):
        PendingProposal.create(OperationId.generate(), "   ", expires_at=_future())


def test_proposal_expires_at_before_created_at_raises() -> None:
    past = Timestamp.from_datetime(datetime.now(tz=UTC) - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        PendingProposal.create(OperationId.generate(), "Create task", expires_at=past)


def test_proposal_is_expired() -> None:
    proposal = PendingProposal.create(OperationId.generate(), "Create task", expires_at=_future())
    assert not proposal.is_expired(Timestamp.now())
    assert proposal.is_expired(_future(120))


def test_proposal_consume() -> None:
    proposal = PendingProposal.create(OperationId.generate(), "Create task", expires_at=_future())
    consumed = proposal.consume()
    assert consumed.consumed is True
    assert consumed.version == proposal.version


def test_proposal_revise_increments_version() -> None:
    proposal = PendingProposal.create(OperationId.generate(), "Create task", expires_at=_future())
    revised = proposal.revise("Create task Buy ripe mangoes", expires_at=_future(120))
    assert revised.version == 2
    assert revised.consumed is False
    assert revised.content == "Create task Buy ripe mangoes"


def test_proposal_revise_with_attachment() -> None:
    attachment_id = AttachmentId.generate()
    proposal = PendingProposal.create(OperationId.generate(), "Create task", expires_at=_future())
    revised = proposal.revise(
        "Create task with attachment",
        attachment_ids=(attachment_id,),
        expires_at=_future(120),
    )
    assert revised.attachment_ids == (attachment_id,)
