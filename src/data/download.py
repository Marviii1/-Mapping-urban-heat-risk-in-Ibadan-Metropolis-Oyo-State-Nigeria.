from __future__ import annotations

from pathlib import Path

from src.data.validation import list_matching_files


def find_landsat_files(raw_dir: Path, year: int) -> dict[str, list[Path]]:
    year_text = str(year)
    band_patterns = {
        "temperature": "ST_B10",
        "blue": "SR_B2",
        "green": "SR_B3",
        "red": "SR_B4",
        "nir": "SR_B5",
        "swir1": "SR_B6",
    }
    patterns = {
        role: [
            f"*{year_text}*{band}*.TIF",
            f"*{year_text}*{band}*.tif",
            f"*{band}*{year_text}*.TIF",
            f"*{band}*{year_text}*.tif",
        ]
        for role, band in band_patterns.items()
    }
    files = {
        role: list_matching_files(raw_dir, role_patterns)
        for role, role_patterns in patterns.items()
    }
    return files


def gee_export_placeholder() -> str:
    return (
        "Optional Google Earth Engine export is intentionally not automated here. "
        "Use geemap/ee after authentication to export Landsat Collection 2 Level-2 "
        "bands into data/raw/landsat/."
    )
