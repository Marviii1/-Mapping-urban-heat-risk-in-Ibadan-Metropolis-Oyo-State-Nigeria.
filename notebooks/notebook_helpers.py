from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def add_project_root_to_path() -> Path:
    """Make project modules importable from any notebook working directory."""
    root_text = str(PROJECT_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return PROJECT_ROOT


def project_path(*parts: str | Path) -> Path:
    """Build an absolute path inside the project."""
    return PROJECT_ROOT.joinpath(*map(Path, parts))


def load_yaml_config(path: str | Path) -> dict:
    """Load a YAML config while keeping imports local to the function."""
    import yaml

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    with candidate.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def path_status(paths: dict[str, str | Path]) -> list[dict[str, str]]:
    """Return existence status records that display cleanly as a DataFrame."""
    records = []
    for label, path in paths.items():
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = project_path(candidate)
        records.append(
            {
                "item": label,
                "exists": "yes" if candidate.exists() else "no",
                "path": str(candidate.relative_to(PROJECT_ROOT)),
            }
        )
    return records


def print_path_status(paths: dict[str, str | Path]) -> None:
    for record in path_status(paths):
        marker = "[OK]" if record["exists"] == "yes" else "[MISSING]"
        print(f"{marker} {record['item']}: {record['path']}")


def find_files(folder: str | Path, patterns: Iterable[str]) -> list[Path]:
    """Find matching files under a project folder."""
    root = Path(folder)
    if not root.is_absolute():
        root = project_path(root)
    matches: list[Path] = []
    if root.exists():
        for pattern in patterns:
            matches.extend(root.rglob(pattern))
    return sorted(set(matches))


def command_string(*args: str | Path) -> str:
    """Create a copy-friendly command string."""
    return " ".join(str(arg) for arg in args)


def run_command(args: list[str | Path], dry_run: bool = True) -> subprocess.CompletedProcess | None:
    """Run a project command only when dry_run is False.

    Notebooks default to dry-run mode so users can inspect commands before
    launching long geospatial jobs or Earth Engine exports.
    """
    text = command_string(*args)
    print(f"$ {text}")
    if dry_run:
        print("Dry run only. Set RUN_COMMANDS = True in the notebook to execute.")
        return None
    return subprocess.run([str(arg) for arg in args], cwd=PROJECT_ROOT, check=False, text=True)


def raster_info(path: str | Path) -> dict:
    import rasterio

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    with rasterio.open(candidate) as src:
        return {
            "path": str(candidate.relative_to(PROJECT_ROOT)),
            "crs": str(src.crs),
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": src.dtypes[0],
            "nodata": src.nodata,
            "bounds": tuple(round(v, 3) for v in src.bounds),
        }


def raster_stats(path: str | Path, max_pixels: int = 1_000_000) -> dict:
    import numpy as np
    import rasterio

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    with rasterio.open(candidate) as src:
        array = src.read(1, masked=True)
    compressed = array.compressed()
    if compressed.size > max_pixels:
        compressed = compressed[:: max(1, compressed.size // max_pixels)]
    return {
        "min": float(np.nanmin(compressed)),
        "mean": float(np.nanmean(compressed)),
        "max": float(np.nanmax(compressed)),
        "valid_pixels": int(array.count()),
    }


def plot_raster(path: str | Path, title: str, cmap: str = "inferno") -> None:
    import matplotlib.pyplot as plt
    import rasterio
    from rasterio.plot import show

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    if not candidate.exists():
        print(f"Raster not found: {candidate}")
        return
    with rasterio.open(candidate) as src:
        fig, ax = plt.subplots(figsize=(8, 7))
        show(src, ax=ax, cmap=cmap)
        ax.set_title(title)
        ax.set_axis_off()
        plt.show()


def read_vector(path: str | Path):
    import geopandas as gpd

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(candidate)
    return gpd.read_file(candidate)


def notebook_metadata(title: str, year: int | None = None) -> None:
    meta = {"project_root": str(PROJECT_ROOT), "notebook": title}
    if year is not None:
        meta["analysis_year"] = year
    print(json.dumps(meta, indent=2))
