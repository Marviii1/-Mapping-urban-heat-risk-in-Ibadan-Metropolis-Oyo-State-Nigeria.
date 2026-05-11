from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.download import find_landsat_files, gee_export_placeholder
from src.utils.config import project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate prepared satellite inputs.")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--landsat-dir", type=Path, default=Path("data/raw/landsat"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    landsat_dir = args.landsat_dir if args.landsat_dir.is_absolute() else project_path(args.landsat_dir)
    files = find_landsat_files(landsat_dir, args.year)
    print(f"Checking Landsat inputs for {args.year} in {landsat_dir}")
    missing = []
    for role, paths in files.items():
        if paths:
            print(f"  {role}: {len(paths)} file(s) found")
        else:
            print(f"  {role}: missing")
            missing.append(role)
    if missing:
        print("\nPlace downloaded Landsat Collection 2 Level-2 band files in data/raw/landsat/.")
        print(gee_export_placeholder())
        return 1
    print("Satellite input framework check complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
