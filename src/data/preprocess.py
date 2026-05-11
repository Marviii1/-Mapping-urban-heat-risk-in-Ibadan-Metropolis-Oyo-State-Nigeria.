from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import Resampling, calculate_default_transform, reproject

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def read_boundary(path: str | Path) -> gpd.GeoDataFrame:
    """Read any vector file supported by Fiona/GDAL."""
    return gpd.read_file(path)


def download_file(url: str, destination: Path, chunk_size: int = 1 << 20) -> Path:
    """Download a file from *url* to *destination* with a progress bar.

    Falls back gracefully if *tqdm* is not installed.  Skips the download if
    *destination* already exists and is non-empty.
    """
    import requests

    destination = Path(destination)
    if destination.exists() and destination.stat().st_size > 0:
        LOGGER.info("Already downloaded: %s", destination)
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading %s → %s", url, destination)

    try:
        from tqdm import tqdm
        _tqdm = tqdm
    except ImportError:
        _tqdm = None

    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0)) or None
        ctx: Any = _tqdm(total=total, unit="B", unit_scale=True, desc=destination.name) if _tqdm else _NullContext()
        with ctx as bar, open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=chunk_size):
                fh.write(chunk)
                if _tqdm:
                    bar.update(len(chunk))

    LOGGER.info("Downloaded: %s (%.1f MB)", destination, destination.stat().st_size / 1e6)
    return destination


class _NullContext:
    """No-op context manager used when tqdm is absent."""
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def update(self, n): pass


def extract_zip(zip_path: Path, extract_dir: Path, pattern: str = "*.tif") -> list[Path]:
    """Extract matching files from a ZIP archive and return their paths."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(pattern.lstrip("*"))]
        zf.extractall(extract_dir, members=members)
    extracted = list(extract_dir.rglob(pattern))
    LOGGER.info("Extracted %d file(s) from %s", len(extracted), zip_path.name)
    return sorted(extracted)


# ---------------------------------------------------------------------------
# Raster preparation
# ---------------------------------------------------------------------------


def reproject_raster(source_path: Path, output_path: Path, target_crs: str) -> Path:
    """Reproject a raster to *target_crs* using bilinear resampling."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update(crs=target_crs, transform=transform, width=width, height=height)
        with rasterio.open(output_path, "w", **profile) as dst:
            for band_idx in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=rasterio.band(dst, band_idx),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )
    LOGGER.info("Reprojected → %s", output_path)
    return output_path


def clip_raster_to_boundary(
    raster_path: Path,
    boundary_path: Path,
    output_path: Path,
    nodata: float = -9999.0,
) -> Path:
    """Clip and mask a raster to a vector boundary polygon, reprojecting the
    boundary to the raster CRS on the fly."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(raster_path) as src:
        boundary = gpd.read_file(boundary_path).to_crs(src.crs)
        geoms = [g.__geo_interface__ for g in boundary.geometry if g is not None]
        clipped, transform = mask(src, geoms, crop=True, nodata=nodata)
        profile = src.profile.copy()
        profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform,
            nodata=nodata,
            compress="deflate",
        )
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(clipped)
    LOGGER.info("Clipped → %s", output_path)
    return output_path


def clip_and_reproject_raster(
    raster_path: Path,
    boundary_path: Path,
    output_path: Path,
    target_crs: str,
    nodata: float = -9999.0,
) -> Path:
    """Reproject then clip a raster.  Uses a temporary file for the intermediate
    reprojected layer so the original is never modified."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "reprojected.tif"
        reproject_raster(raster_path, tmp_path, target_crs)
        clip_raster_to_boundary(tmp_path, boundary_path, output_path, nodata)
    return output_path


def resample_to_match(
    source_path: Path,
    reference_path: Path,
    output_path: Path,
    resampling: Resampling = Resampling.bilinear,
) -> Path:
    """Resample *source_path* to match the resolution, extent, and CRS of
    *reference_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(reference_path) as ref, rasterio.open(source_path) as src:
        profile = ref.profile.copy()
        profile.update(count=src.count, dtype="float32", compress="deflate")
        with rasterio.open(output_path, "w", **profile) as dst:
            for band_idx in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=rasterio.band(dst, band_idx),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref.transform,
                    dst_crs=ref.crs,
                    resampling=resampling,
                )
    LOGGER.info("Resampled to match %s → %s", reference_path.name, output_path)
    return output_path


def apply_landsat_sr_scale(array: np.ndarray, nodata_value: float = -9999.0) -> np.ndarray:
    """Convert Landsat Collection 2 Level-2 SR raw DN to surface reflectance.

    Formula: reflectance = DN × 0.0000275 + (−0.2)
    Valid range is clamped to [0, 1].  Nodata pixels are preserved as NaN.
    """
    result = array.astype("float32")
    valid = result != nodata_value
    result[valid] = result[valid] * 0.0000275 - 0.2
    result[valid] = np.clip(result[valid], 0.0, 1.0)
    result[~valid] = np.nan
    return result
