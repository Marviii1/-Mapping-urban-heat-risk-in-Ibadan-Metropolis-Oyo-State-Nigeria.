from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.uhi.intensity import compute_uhi_from_rural_reference
from src.utils.config import project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute UHI intensity from rural reference pixels.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--reference", choices=["auto"], default="auto")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lst = project_path(f"data/processed/lst/lst_ibadan_{args.year}_celsius.tif")
    ndvi = project_path(f"data/processed/indices/ndvi_{args.year}.tif")
    ndbi = project_path(f"data/processed/indices/ndbi_{args.year}.tif")
    for path in [lst, ndvi, ndbi]:
        if not path.exists():
            print(f"Required input missing: {path}")
            return 1
    intensity, classes, mean_rural = compute_uhi_from_rural_reference(
        lst,
        ndvi,
        ndbi,
        project_path(f"data/processed/uhi/uhi_intensity_{args.year}.tif"),
        project_path(f"data/processed/uhi/uhi_classes_{args.year}.tif"),
    )
    print(f"Mean rural LST reference: {mean_rural:.2f} C")
    print(f"UHI intensity saved: {intensity}")
    print(f"UHI classes saved: {classes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
