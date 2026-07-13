"""Regression tests for the LangChain-only model integration boundary."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "mango_agent"


def test_mango_source_does_not_import_anthropic_sdk() -> None:
    violations: list[str] = []

    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                continue

            if any(module == "anthropic" or module.startswith("anthropic.") for module in modules):
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []


def test_anthropic_sdk_is_not_a_direct_project_dependency() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]

    assert not any(
        dependency.split("[", 1)[0].startswith("anthropic") for dependency in dependencies
    )
