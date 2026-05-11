from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from src.utils.raster_utils import safe_divide, write_raster


def _read_reference(path: Path) -> tuple[np.ndarray, dict]:
    """Read the reference band and return array/profile for output rasters."""
    with rasterio.open(path) as src:
        array = src.read(1).astype("float32")
        profile = src.profile.copy()
        nodata = src.nodata
    if nodata is not None:
        array[array == nodata] = np.nan
    return array, profile


def _read_aligned_band(path: Path, reference_profile: dict) -> np.ndarray:
    """Read a raster band aligned to the reference profile.

    Landsat bands exported separately from Earth Engine can have slightly
    different extents, transforms, or array sizes after clipping. Index
    formulas require pixel-to-pixel arithmetic, so every band is warped onto
    one shared grid before calculation.
    """
    destination = np.full(
        (reference_profile["height"], reference_profile["width"]),
        np.nan,
        dtype="float32",
    )
    with rasterio.open(path) as src:
        source = src.read(1).astype("float32")
        if src.nodata is not None:
            source[source == src.nodata] = np.nan

        same_grid = (
            src.crs == reference_profile["crs"]
            and src.transform == reference_profile["transform"]
            and src.width == reference_profile["width"]
            and src.height == reference_profile["height"]
        )
        if same_grid:
            return source

        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=reference_profile["transform"],
            dst_crs=reference_profile["crs"],
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    return destination


def compute_indices(
    blue_path: Path,
    green_path: Path,
    red_path: Path,
    nir_path: Path,
    swir1_path: Path,
    output_dir: Path,
    year: int,
) -> dict[str, Path]:
    red, profile = _read_reference(red_path)
    blue = _read_aligned_band(blue_path, profile)
    green = _read_aligned_band(green_path, profile)
    nir = _read_aligned_band(nir_path, profile)
    swir1 = _read_aligned_band(swir1_path, profile)

    indices = {
        "ndvi": safe_divide(nir - red, nir + red),
        "ndbi": safe_divide(swir1 - nir, swir1 + nir),
        "mndwi": safe_divide(green - swir1, green + swir1),
        "bsi": safe_divide((swir1 + red) - (nir + blue), (swir1 + red) + (nir + blue)),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        name: write_raster(output_dir / f"{name}_{year}.tif", array, profile)
        for name, array in indices.items()
    }
