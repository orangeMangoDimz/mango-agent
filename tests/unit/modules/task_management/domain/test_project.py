from __future__ import annotations

import pytest

from mango_agent.modules.task_management.domain.project import Project
from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.domain.ids import UserId


def test_project_create() -> None:
    owner = UserId.generate()
    project = Project.create(owner, "Mango")
    assert project.owner_user_id == owner
    assert project.title == "Mango"
    assert project.created_at == project.updated_at


def test_project_empty_title_raises() -> None:
    with pytest.raises(ValidationError):
        Project.create(UserId.generate(), "   ")


def test_project_rename() -> None:
    project = Project.create(UserId.generate(), "Mango")
    before = project.updated_at
    renamed = project.rename("Mango Agent")
    assert renamed.title == "Mango Agent"
    assert renamed.updated_at is not before
    assert renamed.id == project.id
    assert renamed.created_at == project.created_at


def test_project_rename_empty_raises() -> None:
    project = Project.create(UserId.generate(), "Mango")
    with pytest.raises(ValidationError):
        project.rename("   ")
