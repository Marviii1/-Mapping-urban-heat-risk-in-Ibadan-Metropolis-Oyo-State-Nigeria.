"""Export GHSL built-up surface for only the Ibadan study area from Earth Engine.

This avoids downloading the very large global GHSL ZIP. It exports the
``built_surface`` band from:

    JRC/GHSL/P2023A/GHS_BUILT_S/{year}

to Google Drive, clipped to:

    data/processed/uhi/ibadan_metropolitan_boundary.gpkg

After downloading the exported GeoTIFF from Drive into ``data/raw/ghsl/``, run:

    python scripts/02c_prepare_ghsl.py --year 2023 --input-raster data/raw/ghsl/GHSL_BUILT_S_2023_IBADAN.tif
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

LOGGER = logging.getLogger(__name__)

GHSL_COLLECTION = "JRC/GHSL/P2023A/GHS_BUILT_S"
DEFAULT_BOUNDARY = Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg")


def project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_project(cli_value: str | None) -> str | None:
    if cli_value:
        return cli_value.strip()

    for variable in ("EE_PROJECT", "GOOGLE_CLOUD_PROJECT"):
        value = os.environ.get(variable, "").strip()
        if value:
            LOGGER.info("Using Earth Engine project from %s: %s", variable, value)
            return value

    credentials = Path.home() / ".config" / "earthengine" / "credentials"
    if credentials.exists():
        try:
            data = json.loads(credentials.read_text(encoding="utf-8"))
            value = data.get("project_id") or data.get("project")
            if value:
                return str(value).strip()
        except Exception:
            pass

    return None


def initialize_ee(project: str | None) -> bool:
    import ee

    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        LOGGER.info("Earth Engine initialized.")
        return True
    except Exception:
        LOGGER.info("Earth Engine credentials missing or expired. Opening authentication flow.")
        try:
            ee.Authenticate()
            if project:
                ee.Initialize(project=project)
            else:
                ee.Initialize()
            return True
        except Exception as exc:
            print(f"ERROR: Earth Engine authentication failed: {exc}")
            return False


def load_boundary_geometry(boundary_path: Path, layer: str | None, simplify_tolerance: float):
    import ee
    import geopandas as gpd
    from shapely.geometry import mapping

    resolved = project_path(boundary_path)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Boundary not found: {resolved}. Prepare/import the Ibadan boundary first."
        )

    kwargs = {"layer": layer} if layer else {}
    gdf = gpd.read_file(resolved, **kwargs)
    if gdf.empty:
        raise ValueError(f"Boundary contains no features: {resolved}")
    if gdf.crs is None:
        raise ValueError(f"Boundary has no CRS: {resolved}")

    geometry = gdf.to_crs("EPSG:4326").geometry.unary_union
    if simplify_tolerance > 0:
        geometry = geometry.simplify(simplify_tolerance, preserve_topology=True)
    return ee.Geometry(mapping(geometry))


def export_ghsl(
    year: int,
    region,
    drive_folder: str,
    dry_run: bool,
) -> str:
    import ee

    # GHSL built-up surface is provided at five-year epochs. Use nearest epoch
    # when a non-epoch analysis year is requested.
    epochs = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]
    epoch = year if year in epochs else min(epochs, key=lambda value: abs(value - year))
    if epoch != year:
        LOGGER.warning("GHSL has no %d epoch. Using %d as proxy.", year, epoch)

    image = ee.Image(f"{GHSL_COLLECTION}/{epoch}").select("built_surface").clip(region)
    description = f"GHSL_BUILT_S_{year}_IBADAN"

    if dry_run:
        LOGGER.info("[dry-run] Would export %s to Drive folder %s", description, drive_folder)
        return "dry-run"

    task = ee.batch.Export.image.toDrive(
        image=image.toFloat(),
        description=description,
        folder=drive_folder,
        fileNamePrefix=description,
        region=region,
        scale=100,
        crs="EPSG:32631",
        maxPixels=1_000_000_000,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    task.start()
    return task.id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export GHSL built-up surface for Ibadan only.")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--project", default=None, help="Google Cloud Earth Engine project ID.")
    parser.add_argument("--drive-folder", default="ibadan_heat_risk")
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--boundary-layer", default=None)
    parser.add_argument("--simplify-tolerance", type=float, default=0.0001)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    try:
        import ee  # noqa: F401
    except ImportError:
        print("ERROR: earthengine-api is not installed. Run: pip install earthengine-api")
        return 1

    project = resolve_project(args.project)
    if not project:
        print("ERROR: No Earth Engine project found. Pass --project YOUR_PROJECT_ID.")
        return 1
    if not initialize_ee(project):
        return 1

    try:
        region = load_boundary_geometry(args.boundary, args.boundary_layer, args.simplify_tolerance)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    task_id = export_ghsl(args.year, region, args.drive_folder, args.dry_run)
    print(f"GHSL export submitted: {task_id}")
    print(f"Drive folder: {args.drive_folder}")
    print("\nAfter it completes, download the GeoTIFF into data/raw/ghsl/ and run:")
    print(
        "  python scripts/02c_prepare_ghsl.py "
        f"--year {args.year} --input-raster data/raw/ghsl/GHSL_BUILT_S_{args.year}_IBADAN.tif"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
