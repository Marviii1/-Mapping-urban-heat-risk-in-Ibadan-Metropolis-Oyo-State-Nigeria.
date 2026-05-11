from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(*parts: str | Path) -> Path:
    """Return a path rooted at the project directory."""
    return PROJECT_ROOT.joinpath(*map(Path, parts))


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file using a path relative to the project root or absolute path."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    if not candidate.exists():
        raise FileNotFoundError(f"Configuration file not found: {candidate}")
    with candidate.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def ensure_directory(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate
