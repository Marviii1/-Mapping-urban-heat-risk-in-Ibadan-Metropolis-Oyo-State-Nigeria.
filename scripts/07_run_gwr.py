from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
from shapely.geometry import box

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.modelling.diagnostics import write_model_diagnostics
from src.modelling.gwr_model import run_gwr
from src.utils.config import load_yaml, project_path
from src.utils.vector_utils import create_regular_grid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GWR heat driver model.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--dependent", default="lst")
    parser.add_argument("--predictors", nargs="+", required=True)
    parser.add_argument("--population-raster", type=Path)
    parser.add_argument("--builtup-raster", type=Path)
    parser.add_argument(
        "--resolution",
        type=float,
        default=500.0,
        help="GWR modelling grid resolution in metres (default: 500).",
    )
    parser.add_argument(
        "--max-cells",
        type=int,
        default=30_000,
        help="Safety limit for model grid cells before fitting GWR.",
    )
    parser.add_argument(
        "--allow-large-grid",
        action="store_true",
        help="Run even when grid cell count exceeds --max-cells.",
    )
    parser.add_argument(
        "--bandwidth",
        type=int,
        default=None,
        help=(
            "Force an adaptive GWR bandwidth in number of nearest-neighbor grid cells. "
            "If omitted, bandwidth is selected automatically."
        ),
    )
    parser.add_argument(
        "--diagnostics-only",
        action="store_true",
        help="Write correlation, VIF, and global OLS diagnostics without fitting GWR.",
    )
    return parser.parse_args()


def raster_for_variable(name: str, year: int, args: argparse.Namespace) -> Path:
    lookup = {
        "lst": project_path(f"data/processed/lst/lst_ibadan_{year}_celsius.tif"),
        "ndvi": project_path(f"data/processed/indices/ndvi_{year}.tif"),
        "ndbi": project_path(f"data/processed/indices/ndbi_{year}.tif"),
        "population_density": args.population_raster
        or project_path(f"data/processed/vulnerability/population_density_{year}.tif"),
        "built_up_density": args.builtup_raster
        or project_path(f"data/processed/vulnerability/built_up_density_{year}.tif"),
    }
    return lookup[name]


def boundary_intersecting_all_rasters(
    boundary: gpd.GeoDataFrame,
    rasters: dict[str, Path],
    projected_crs: str,
) -> gpd.GeoDataFrame:
    """Clip the study boundary to the common extent of all model rasters."""
    if boundary.crs is None:
        raise ValueError("Study boundary has no CRS.")

    analysis_area = boundary.to_crs(projected_crs)[["geometry"]]
    for name, raster_path in rasters.items():
        with rasterio.open(raster_path) as src:
            bounds = gpd.GeoDataFrame(geometry=[box(*src.bounds)], crs=src.crs).to_crs(projected_crs)
        analysis_area = gpd.overlay(analysis_area, bounds, how="intersection")
        analysis_area = analysis_area[~analysis_area.geometry.is_empty & analysis_area.geometry.notna()].copy()
        if analysis_area.empty:
            raise ValueError(f"No common overlap between boundary and raster '{name}': {raster_path}")
    return analysis_area


def sample_raster_mean(grid: gpd.GeoDataFrame, raster_path: Path) -> list[float | None]:
    """Sample raster means using a temporary grid in the raster CRS."""
    with rasterio.open(raster_path) as src:
        sampling_grid = grid.to_crs(src.crs)
    try:
        stats = zonal_stats(sampling_grid, raster_path, stats=["mean"], nodata=-9999, boundless=True)
    except TypeError:
        stats = zonal_stats(sampling_grid, raster_path, stats=["mean"], nodata=-9999)
    return [item["mean"] for item in stats]


def main() -> int:
    args = parse_args()
    cfg = load_yaml("config/project_config.yml")
    boundary_path = project_path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg")
    if not boundary_path.exists():
        print("Prepared study boundary missing. Run scripts/01_prepare_study_area.py first.")
        return 1

    variables = [args.dependent, *args.predictors]
    rasters = {name: raster_for_variable(name, args.year, args) for name in variables}
    missing = [f"{name}: {path}" for name, path in rasters.items() if not Path(path).exists()]
    if missing:
        print("Missing raster input(s) for GWR:")
        for item in missing:
            print(f"  - {item}")
        return 1

    boundary = gpd.read_file(boundary_path)
    try:
        analysis_boundary = boundary_intersecting_all_rasters(
            boundary,
            rasters,
            cfg["project"]["crs_projected"],
        )
    except Exception as exc:
        print(f"Could not align boundary with model rasters: {exc}")
        return 1

    grid = create_regular_grid(analysis_boundary, args.resolution)
    grid = grid[~grid.geometry.is_empty & grid.geometry.notna()].copy()
    grid = grid[grid.geometry.area > 0].copy()
    print(f"GWR grid cells intersecting all rasters: {len(grid):,}")
    print(f"GWR grid resolution: {args.resolution:g} m")
    if len(grid) > args.max_cells and not args.allow_large_grid:
        print(
            "\nGrid is too large for practical GWR. "
            f"Current cells: {len(grid):,}; limit: {args.max_cells:,}."
        )
        print("Use a coarser grid, for example:")
        print(
            f"  python scripts/07_run_gwr.py --year {args.year} --dependent {args.dependent} "
            f"--predictors {' '.join(args.predictors)} --resolution 1000"
        )
        return 1

    for name, raster in rasters.items():
        column = name if name != "lst" else "lst"
        print(f"Sampling {column}: {raster}")
        grid[column] = sample_raster_mean(grid, raster)

    out_dir = project_path("data/processed/gwr")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_grid = out_dir / f"model_grid_{args.year}.gpkg"
    grid.to_file(model_grid, layer="model_grid", driver="GPKG")

    diagnostics = write_model_diagnostics(
        grid,
        dependent=args.dependent,
        predictors=args.predictors,
        output_dir=out_dir,
        year=args.year,
    )
    print(f"Complete model observations: {diagnostics['complete_observations']:,}")
    print(f"Correlation matrix saved: {diagnostics['correlation_path']}")
    print(f"VIF table saved: {diagnostics['vif_path']}")
    print(f"Global OLS coefficients saved: {diagnostics['ols_table_path']}")
    print(f"Global OLS summary saved: {diagnostics['ols_summary_path']}")
    print("\nVIF diagnostics:")
    print(diagnostics["vif"].to_string(index=False))
    print("\nGlobal OLS coefficient diagnostics:")
    print(diagnostics["ols_table"].to_string(index=False))

    if args.diagnostics_only:
        print("\nDiagnostics-only mode complete. GWR was not fitted.")
        return 0

    if args.bandwidth is not None:
        print(f"\nUsing forced adaptive bandwidth: {args.bandwidth} nearest neighbors")

    results_path, summary_path, summary_text = run_gwr(
        grid,
        dependent=args.dependent,
        predictors=args.predictors,
        output_path=out_dir / f"gwr_results_{args.year}.gpkg",
        summary_path=out_dir / f"gwr_summary_{args.year}.txt",
        bandwidth=args.bandwidth,
    )
    print("\n" + summary_text)
    print(f"Model grid saved: {model_grid}")
    print(f"GWR results saved: {results_path}")
    print(f"GWR summary saved: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
