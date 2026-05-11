from __future__ import annotations

from pathlib import Path


def require_file(path: str | Path, message: str | None = None) -> Path:
    candidate = Path(path)
    if not candidate.exists():
        raise FileNotFoundError(message or f"Required file not found: {candidate}")
    return candidate


def list_matching_files(directory: str | Path, patterns: list[str]) -> list[Path]:
    root = Path(directory)
    if not root.exists():
        return []
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(root.rglob(pattern))
    return sorted(set(matches))
