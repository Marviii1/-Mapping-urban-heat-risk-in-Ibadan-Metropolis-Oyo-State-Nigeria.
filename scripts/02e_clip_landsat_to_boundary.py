"""Clip downloaded Landsat band rasters to the prepared Ibadan boundary.

Use this after downloading Google Earth Engine exports if the GeoTIFFs still
display as rectangular rasters in QGIS or include valid pixels outside the
study boundary.

Example
-------
    python scripts/02e_clip_landsat_to_boundary.py --years 2015 2020 2023

Outputs
-------
    data/raw/landsat_clipped/
        ST_B10_2023.tif
        SR_B2_2023.tif
        ...
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.download import find_landsat_files
from src.utils.config import project_path
from src.utils.raster_utils import clip_raster_to_vector


BAND_ORDER = ("temperature", "blue", "green", "red", "nir", "swir1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clip downloaded Landsat rasters to the prepared Ibadan boundary."
    )
    parser.add_argument("--years", nargs="+", type=int, default=[2015, 2020, 2023])
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw/landsat"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/landsat_clipped"))
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg"),
    )
    parser.add_argument(
        "--overwrite-raw",
        action="store_true",
        help=(
            "Replace files in --input-dir with clipped rasters and move originals to "
            "data/raw/landsat_unclipped_backup/. Default is safer: write to --output-dir."
        ),
    )
    return parser.parse_args()


def clipped_name(source: Path, year: int) -> str:
    upper = source.name.upper()
    for band in ("ST_B10", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6"):
        if band in upper:
            return f"{band}_{year}.tif"
    return source.name


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir if args.input_dir.is_absolute() else project_path(args.input_dir)
    output_dir = args.output_dir if args.output_dir.is_absolute() else project_path(args.output_dir)
    boundary = args.boundary if args.boundary.is_absolute() else project_path(args.boundary)

    if not boundary.exists():
        print(f"Boundary not found: {boundary}")
        print("Run the study-area preparation/import script first.")
        return 1
    if not input_dir.exists():
        print(f"Landsat input directory not found: {input_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = project_path("data/raw/landsat_unclipped_backup")
    if args.overwrite_raw:
        backup_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    missing_messages: list[str] = []
    for year in args.years:
        files = find_landsat_files(input_dir, year)
        print(f"\nYear {year}")
        for role in BAND_ORDER:
            matches = files.get(role, [])
            if not matches:
                missing_messages.append(f"{year}: missing {role}")
                print(f"  missing {role}")
                continue

            source = matches[0]
            destination = output_dir / clipped_name(source, year)
            clip_raster_to_vector(source, boundary, destination)
            total += 1
            print(f"  clipped {source.name} -> {destination.relative_to(PROJECT_ROOT)}")

            if args.overwrite_raw:
                backup = backup_dir / source.name
                if not backup.exists():
                    shutil.move(str(source), str(backup))
                shutil.copy2(destination, source)
                print(f"    raw replaced; original backup: {backup.relative_to(PROJECT_ROOT)}")

    print(f"\nClipped {total} raster file(s).")
    if missing_messages:
        print("Missing inputs:")
        for message in missing_messages:
            print(f"  - {message}")
    if not args.overwrite_raw:
        print(f"\nUse clipped rasters with:")
        for year in args.years:
            print(f"  python scripts/03_compute_lst.py --year {year} --landsat-dir data/raw/landsat_clipped")
            print(f"  python scripts/04_compute_urban_indices.py --year {year} --landsat-dir data/raw/landsat_clipped")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
