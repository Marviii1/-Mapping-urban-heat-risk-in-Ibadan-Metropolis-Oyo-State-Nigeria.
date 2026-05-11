from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.download import find_landsat_files
from src.remote_sensing.indices import compute_indices
from src.utils.config import project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute NDVI, NDBI, MNDWI, and BSI.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--landsat-dir",
        type=Path,
        default=Path("data/raw/landsat"),
        help="Directory containing Landsat band GeoTIFFs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    landsat_dir = args.landsat_dir if args.landsat_dir.is_absolute() else project_path(args.landsat_dir)
    files = find_landsat_files(landsat_dir, args.year)
    required = ["blue", "green", "red", "nir", "swir1"]
    missing = [name for name in required if not files[name]]
    if missing:
        print("Missing required Landsat reflectance bands: " + ", ".join(missing))
        print(f"Expected SR_B2, SR_B3, SR_B4, SR_B5, and SR_B6 files in {landsat_dir}.")
        return 1
    outputs = compute_indices(
        blue_path=files["blue"][0],
        green_path=files["green"][0],
        red_path=files["red"][0],
        nir_path=files["nir"][0],
        swir1_path=files["swir1"][0],
        output_dir=project_path("data/processed/indices"),
        year=args.year,
    )
    for name, path in outputs.items():
        print(f"{name.upper()} saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
