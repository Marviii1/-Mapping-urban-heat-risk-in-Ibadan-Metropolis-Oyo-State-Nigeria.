from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.download import find_landsat_files
from src.remote_sensing.lst import compute_clipped_lst
from src.utils.config import load_yaml, project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute Landsat-derived LST for Ibadan.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--thermal-band", type=Path)
    parser.add_argument(
        "--landsat-dir",
        type=Path,
        default=Path("data/raw/landsat"),
        help="Directory containing Landsat band GeoTIFFs.",
    )
    parser.add_argument("--boundary", type=Path, default=Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg"))
    parser.add_argument(
        "--thermal-units",
        choices=["auto", "raw_dn", "kelvin", "celsius"],
        default="auto",
        help=(
            "Units of the ST_B10 input. Use auto unless you know the export is raw DN, "
            "Kelvin, or Celsius."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_yaml("config/lst_config.yml")["lst"]
    thermal = args.thermal_band
    if thermal is None:
        landsat_dir = args.landsat_dir if args.landsat_dir.is_absolute() else project_path(args.landsat_dir)
        matches = find_landsat_files(landsat_dir, args.year)["temperature"]
        if not matches:
            print(f"No ST_B10 thermal band found in {landsat_dir}.")
            print("Add Landsat files there, pass --landsat-dir, or pass --thermal-band.")
            return 1
        thermal = matches[0]
    thermal = thermal if thermal.is_absolute() else project_path(thermal)
    boundary = args.boundary if args.boundary.is_absolute() else project_path(args.boundary)
    output = project_path(f"data/processed/lst/lst_ibadan_{args.year}_celsius.tif")
    print(f"Using thermal band: {thermal}")
    compute_clipped_lst(
        thermal,
        boundary,
        output,
        cfg["scale_factor"],
        cfg["add_offset"],
        units=args.thermal_units,
    )
    print(f"LST raster saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
