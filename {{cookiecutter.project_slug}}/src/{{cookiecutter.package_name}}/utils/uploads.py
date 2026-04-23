"""Helpers for referencing uploaded files from agent tools."""

from __future__ import annotations

from pathlib import Path

from {{ cookiecutter.package_name }}.config import get_settings


def get_upload_path(file_id: str) -> Path | None:
    """Find an uploaded file by its ID prefix.

    Returns the path to the file, or ``None`` if not found.
    """
    upload_dir = Path(get_settings().upload_dir)
    if not upload_dir.exists():
        return None
    matches = list(upload_dir.glob(f"{file_id}_*"))
    return matches[0] if matches else None


def read_upload_text(file_id: str) -> str | None:
    """Read the text content of an uploaded file.

    Returns ``None`` if the file does not exist.
    """
    path = get_upload_path(file_id)
    if path is None:
        return None
    return path.read_text()
