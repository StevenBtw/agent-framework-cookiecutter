"""Shared fixtures for cookiecutter template tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterator

import pytest
from cookiecutter.main import cookiecutter

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def generate(tmp_path: Path) -> Callable[..., Path]:
    """Return a callable that generates a project into tmp_path.

    Usage::

        project_dir = generate(governance_level="minimal")
        assert (project_dir / "policies.yaml").exists()
    """

    def _generate(**overrides: str) -> Path:
        context = {
            "project_name": "Test Agent",
            "project_slug": "test-agent",
            "package_name": "test_agent",
            "author": "Test",
            "author_email": "test@example.com",
            "description": "A test agent",
            "python_version": "3.14",
            "memory_provider": "grafeo-memory",
            "model_provider": "pydantic_ai_custom",
            "interface": "both",
            "auth_method": "bearer_token",
            "governance_level": "none",
        }
        context.update(overrides)
        cookiecutter(
            str(REPO_ROOT),
            no_input=True,
            output_dir=str(tmp_path),
            extra_context=context,
        )
        return tmp_path / context["project_slug"]

    return _generate
