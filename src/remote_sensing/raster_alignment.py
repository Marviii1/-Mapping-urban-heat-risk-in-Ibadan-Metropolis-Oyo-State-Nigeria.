from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject


def reproject_match(source_path: Path, reference_path: Path, output_path: Path) -> Path:
    with rasterio.open(reference_path) as ref, rasterio.open(source_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, ref.crs, src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update(crs=ref.crs, transform=transform, width=width, height=height)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            for index in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, index),
                    destination=rasterio.band(dst, index),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=ref.crs,
                    resampling=Resampling.bilinear,
                )
    return output_path
