from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from rasterstats import zonal_stats
from shapely.geometry import box

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.spatial_stats.hotspots import getis_ord_gistar
from src.spatial_stats.lisa import local_moran_clusters
from src.spatial_stats.moran import global_moran
from src.utils.config import load_yaml, project_path
from src.utils.vector_utils import create_regular_grid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Moran's I, LISA, and Gi* analysis.")
    parser.add_argument("--target", choices=["lst", "uhi"], default="lst")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--resolution",
        type=float,
        default=None,
        help="ESDA grid resolution in metres. Defaults to config analysis.grid_resolution_m.",
    )
    parser.add_argument(
        "--max-cells",
        type=int,
        default=50_000,
        help="Safety limit for ESDA grid cells. Increase only if your machine can handle it.",
    )
    parser.add_argument(
        "--allow-large-grid",
        action="store_true",
        help="Run even when grid cell count exceeds --max-cells.",
    )
    return parser.parse_args()


def target_raster(target: str, year: int) -> Path:
    if target == "lst":
        return project_path(f"data/processed/lst/lst_ibadan_{year}_celsius.tif")
    return project_path(f"data/processed/uhi/uhi_intensity_{year}.tif")


def boundary_intersecting_raster(
    boundary: gpd.GeoDataFrame,
    raster_path: Path,
    projected_crs: str,
) -> tuple[gpd.GeoDataFrame, object]:
    """Return boundary clipped to raster bounds, in the projected analysis CRS.

    This prevents rasterstats from requesting invalid read windows when the
    vector grid extends beyond a cropped raster extent. The output is kept in
    the projected CRS so grid_resolution_m is interpreted in metres.
    """
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        raster_bounds = gpd.GeoDataFrame(geometry=[box(*src.bounds)], crs=raster_crs)

    if boundary.crs is None:
        raise ValueError("Study boundary has no CRS.")

    boundary_projected = boundary.to_crs(projected_crs)
    bounds_projected = raster_bounds.to_crs(projected_crs)
    clipped = gpd.overlay(boundary_projected[["geometry"]], bounds_projected, how="intersection")
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()].copy()
    if clipped.empty:
        raise ValueError("Study boundary does not intersect the target raster extent.")
    return clipped, raster_crs


def main() -> int:
    args = parse_args()
    cfg = load_yaml("config/project_config.yml")
    raster = target_raster(args.target, args.year)
    boundary_path = project_path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg")
    if not raster.exists():
        print(f"Target raster missing: {raster}")
        return 1
    if not boundary_path.exists():
        print("Prepared study boundary missing. Run scripts/01_prepare_study_area.py first.")
        return 1

    boundary = gpd.read_file(boundary_path)
    try:
        analysis_boundary, raster_crs = boundary_intersecting_raster(
            boundary,
            raster,
            cfg["project"]["crs_projected"],
        )
    except Exception as exc:
        print(f"Could not align boundary with raster extent: {exc}")
        return 1

    resolution = args.resolution or cfg["analysis"]["grid_resolution_m"]
    grid = create_regular_grid(analysis_boundary, resolution)
    grid = grid[~grid.geometry.is_empty & grid.geometry.notna()].copy()
    grid = grid[grid.geometry.area > 0].copy()
    print(f"ESDA grid cells intersecting raster: {len(grid):,}")
    print(f"ESDA grid resolution: {resolution:g} m")

    if len(grid) > args.max_cells and not args.allow_large_grid:
        print(
            "\nGrid is too large for practical Moran/LISA/Gi* analysis. "
            f"Current cells: {len(grid):,}; limit: {args.max_cells:,}."
        )
        print("Use a coarser ESDA grid, for example:")
        print(f"  python scripts/06_run_esda.py --target {args.target} --year {args.year} --resolution 500")
        print(f"  python scripts/06_run_esda.py --target {args.target} --year {args.year} --resolution 1000")
        print("\nUse --allow-large-grid only if you intentionally want the heavy run.")
        return 1

    # Rasterstats expects vector geometries in the raster CRS. Keep the original
    # projected grid for spatial weights and outputs, but sample with a temporary
    # raster-CRS copy.
    sampling_grid = grid.to_crs(raster_crs)
    try:
        stats = zonal_stats(sampling_grid, raster, stats=["mean"], nodata=-9999, boundless=True)
    except TypeError:
        stats = zonal_stats(sampling_grid, raster, stats=["mean"], nodata=-9999)
    grid[f"{args.target}_mean"] = [item["mean"] for item in stats]
    grid = grid.dropna(subset=[f"{args.target}_mean"]).copy()
    if len(grid) < 5:
        print("Not enough grid cells with raster values for ESDA.")
        return 1

    moran = global_moran(grid, f"{args.target}_mean")
    lisa = local_moran_clusters(grid, f"{args.target}_mean")
    gistar = getis_ord_gistar(grid, f"{args.target}_mean")

    out_dir = project_path("data/processed/esda")
    table_dir = project_path("data/processed/tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    moran_path = out_dir / f"morans_i_{args.year}.csv"
    pd.DataFrame([moran]).to_csv(moran_path, index=False)
    lisa_path = out_dir / f"lisa_clusters_{args.year}.gpkg"
    gi_path = out_dir / f"gistar_hotspots_{args.year}.gpkg"
    lisa.to_file(lisa_path, layer="lisa_clusters", driver="GPKG")
    gistar.to_file(gi_path, layer="gistar_hotspots", driver="GPKG")
    grid.to_file(out_dir / f"esda_grid_{args.year}.gpkg", layer="esda_grid", driver="GPKG")

    print(f"Global Moran's I saved: {moran_path}")
    print(f"LISA clusters saved: {lisa_path}")
    print(f"Gi* hot spots saved: {gi_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
