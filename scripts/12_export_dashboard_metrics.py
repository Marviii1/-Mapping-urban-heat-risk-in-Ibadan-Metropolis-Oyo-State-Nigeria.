"""Export small CSV metrics used by the Streamlit Cloud dashboard.

The web deployment can use PNG maps as raster proxies, but the metric cards and
charts need compact tabular summaries. Run this locally after analysis outputs
are generated, then commit the resulting files in ``outputs/tables``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.uhi.classification import classify_uhi_with_stats


RASTER_LAYERS = {
    "Land Surface Temperature": "data/processed/lst/lst_ibadan_{year}_celsius.tif",
    "Urban Heat Island Intensity": "data/processed/uhi/uhi_intensity_{year}.tif",
    "Normalized Difference Vegetation Index": "data/processed/indices/ndvi_{year}.tif",
    "Normalized Difference Built-up Index": "data/processed/indices/ndbi_{year}.tif",
    "Heat Vulnerability Index": "data/processed/vulnerability/heat_vulnerability_index_{year}.tif",
    "Heat Exposure Index": "data/processed/vulnerability/heat_exposure_index_{year}.tif",
    "Sensitivity Index": "data/processed/vulnerability/sensitivity_index_{year}.tif",
    "Adaptive Capacity Index": "data/processed/vulnerability/adaptive_capacity_index_{year}.tif",
}


def read_valid(path: Path) -> tuple[np.ndarray, float] | tuple[None, None]:
    if not path.exists():
        return None, None
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        pixel_area_km2 = abs(src.transform.a * src.transform.e) / 1_000_000
    valid = arr[np.isfinite(arr)]
    return valid, pixel_area_km2


def export_summary_stats(year: int) -> Path:
    records = []
    for label, template in RASTER_LAYERS.items():
        path = PROJECT_ROOT / template.format(year=year)
        valid, _ = read_valid(path)
        if valid is None or valid.size == 0:
            continue
        records.append({
            "year": year,
            "layer": label,
            "min": float(np.nanmin(valid)),
            "mean": float(np.nanmean(valid)),
            "max": float(np.nanmax(valid)),
            "std": float(np.nanstd(valid)),
            "valid_pixels": int(valid.size),
        })
    out = PROJECT_ROOT / "outputs" / "tables" / f"dashboard_summary_stats_{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(out, index=False)
    return out


def export_uhi_classes(year: int) -> Path | None:
    path = PROJECT_ROOT / f"data/processed/uhi/uhi_intensity_{year}.tif"
    if not path.exists():
        return None
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        pixel_area_km2 = abs(src.transform.a * src.transform.e) / 1_000_000
    _, summary = classify_uhi_with_stats(arr, pixel_area_km2=pixel_area_km2)
    summary.insert(0, "year", year)
    out = PROJECT_ROOT / "outputs" / "tables" / f"uhi_class_distribution_{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out, index=False)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Export compact dashboard metric tables.")
    parser.add_argument("--years", nargs="+", type=int, default=[2015, 2023, 2025])
    args = parser.parse_args()

    for year in args.years:
        print(f"Year {year}")
        print(f"  {export_summary_stats(year)}")
        uhi_path = export_uhi_classes(year)
        if uhi_path:
            print(f"  {uhi_path}")
        else:
            print("  UHI raster not found; skipped UHI class distribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
