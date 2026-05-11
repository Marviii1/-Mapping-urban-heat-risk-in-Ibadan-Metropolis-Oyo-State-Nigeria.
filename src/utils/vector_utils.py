from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box


def create_regular_grid(boundary: gpd.GeoDataFrame, resolution_m: float) -> gpd.GeoDataFrame:
    boundary_projected = boundary.copy()
    minx, miny, maxx, maxy = boundary_projected.total_bounds
    cells = []
    for x in np.arange(minx, maxx, resolution_m):
        for y in np.arange(miny, maxy, resolution_m):
            cells.append(box(x, y, x + resolution_m, y + resolution_m))
    grid = gpd.GeoDataFrame(geometry=cells, crs=boundary_projected.crs)
    grid = gpd.overlay(grid, boundary_projected[["geometry"]], how="intersection")
    grid["grid_id"] = range(1, len(grid) + 1)
    return grid


def read_project_boundary(path: str | Path) -> gpd.GeoDataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(f"Prepared Ibadan boundary not found: {path}")
    return gpd.read_file(path)
