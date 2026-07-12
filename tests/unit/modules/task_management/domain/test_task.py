from __future__ import annotations

import pytest

from mango_agent.modules.task_management.domain import Priority, Status, Task
from mango_agent.modules.task_management.domain.note import Note
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import AttachmentId, ProjectId, UserId
from mango_agent.shared.domain.value_objects import Timestamp


def test_task_create() -> None:
    project_id = ProjectId.generate()
    task = Task.create(project_id, "Buy mangoes")
    assert task.project_id == project_id
    assert task.title == "Buy mangoes"
    assert task.status == Status.TODO
    assert task.priority == Priority.MEDIUM
    assert task.done_at is None


def test_task_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        Task.create(ProjectId.generate(), "   ")


def test_task_status_done_sets_done_at() -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    now = Timestamp.now()
    done = task.set_status(Status.DONE, now=now)
    assert done.status == Status.DONE
    assert done.done_at == now
    assert done.updated_at == now


def test_task_status_leaving_done_clears_done_at() -> None:
    now = Timestamp.now()
    task = Task.create(ProjectId.generate(), "Buy mangoes").set_status(Status.DONE, now=now)
    reopened = task.set_status(Status.IN_PROGRESS, now=now)
    assert reopened.status == Status.IN_PROGRESS
    assert reopened.done_at is None


def test_task_status_done_to_done_keeps_done_at() -> None:
    now = Timestamp.now()
    task = Task.create(ProjectId.generate(), "Buy mangoes").set_status(Status.DONE, now=now)
    unchanged = task.set_status(Status.DONE, now=now)
    assert unchanged.done_at == now


def test_task_status_blocked_to_done_sets_done_at() -> None:
    now = Timestamp.now()
    task = Task.create(ProjectId.generate(), "Buy mangoes").set_status(Status.BLOCKED, now=now)
    done = task.set_status(Status.DONE, now=now)
    assert done.done_at == now


def test_task_status_todo_to_in_progress_does_not_set_done_at() -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    in_progress = task.set_status(Status.IN_PROGRESS)
    assert in_progress.status == Status.IN_PROGRESS
    assert in_progress.done_at is None


def test_task_invalid_priority_raises() -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    with pytest.raises(ValidationError):
        task.set_priority("High")


def test_task_invalid_status_raises() -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    with pytest.raises(ValidationError):
        task.set_status("done")


def test_task_assign() -> None:
    by = UserId.generate()
    to = UserId.generate()
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    assigned = task.assign(by, to)
    assert assigned.assigned_by == by
    assert assigned.assigned_to == to


def test_task_add_note() -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    note = Note(user_text="Get the ripe ones")
    updated = task.add_note(note)
    assert updated.notes == (note,)


def test_task_set_tags() -> None:
    task = Task.create(ProjectId.generate(), "Buy mangoes")
    tagged = task.set_tags(frozenset({"shopping", "urgent"}))
    assert tagged.tags == frozenset({"shopping", "urgent"})


def test_task_note_with_image_only_is_valid() -> None:
    attachment_id = AttachmentId.generate()
    note = Note(user_text="", image_attachment_id=attachment_id, r2_object_key="tasks/abc/img.png")
    assert note.image_attachment_id == attachment_id
