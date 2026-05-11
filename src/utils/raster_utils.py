from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask


def read_band(path: str | Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        array = src.read(1).astype("float32")
        profile = src.profile.copy()
        nodata = src.nodata
    if nodata is not None:
        array[array == nodata] = np.nan
    return array, profile


def write_raster(path: str | Path, array: np.ndarray, profile: dict, nodata: float = -9999.0) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = profile.copy()
    profile.update(dtype="float32", count=1, nodata=nodata, compress="deflate")
    data = np.where(np.isfinite(array), array, nodata).astype("float32")
    with rasterio.open(output, "w", **profile) as dst:
        dst.write(data, 1)
    return output


def clip_raster_to_vector(
    raster_path: str | Path,
    vector_path: str | Path,
    output_path: str | Path,
    nodata: float | int | None = None,
) -> Path:
    with rasterio.open(raster_path) as src:
        boundary = gpd.read_file(vector_path).to_crs(src.crs)
        geoms = [geom.__geo_interface__ for geom in boundary.geometry if geom is not None]
        output_nodata = nodata if nodata is not None else src.nodata
        if output_nodata is None:
            output_nodata = -9999.0 if "float" in src.dtypes[0] else 0
        clipped, transform = mask(src, geoms, crop=True, filled=True, nodata=output_nodata)
        profile = src.profile.copy()
        profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform,
            nodata=output_nodata,
            compress="deflate",
        )
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output, "w", **profile) as dst:
            dst.write(clipped)
    return output


def safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / denominator
    result[~np.isfinite(result)] = np.nan
    return result
