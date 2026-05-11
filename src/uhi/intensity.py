from __future__ import annotations

from pathlib import Path

import numpy as np

from src.uhi.classification import classify_uhi
from src.utils.raster_utils import read_band, write_raster


def compute_uhi_from_rural_reference(
    lst_path: Path,
    ndvi_path: Path,
    ndbi_path: Path,
    intensity_path: Path,
    classes_path: Path,
    ndvi_threshold: float = 0.35,
    ndbi_threshold: float = 0.0,
) -> tuple[Path, Path, float]:
    lst, profile = read_band(lst_path)
    ndvi, _ = read_band(ndvi_path)
    ndbi, _ = read_band(ndbi_path)
    rural_mask = (ndvi >= ndvi_threshold) & (ndbi <= ndbi_threshold) & np.isfinite(lst)
    if not rural_mask.any():
        raise ValueError("No rural reference pixels found. Adjust NDVI/NDBI thresholds.")
    mean_rural_lst = float(np.nanmean(lst[rural_mask]))
    uhi = lst - mean_rural_lst
    classes = classify_uhi(uhi)
    write_raster(intensity_path, uhi, profile)
    write_raster(classes_path, classes, profile)
    return intensity_path, classes_path, mean_rural_lst
