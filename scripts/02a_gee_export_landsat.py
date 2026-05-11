"""Export Landsat 8/9 Collection 2 Level-2 dry-season composites from
Google Earth Engine for the Ibadan metropolitan area.

Prerequisites
-------------
1.  Install the API and geemap::

        pip install earthengine-api geemap

2.  Authenticate once::

        python scripts/02a_gee_export_landsat.py --auth-only

3.  Prepare the study-area boundary first, then run the export::

        python scripts/02a_gee_export_landsat.py --years 2015 2020 2023

4.  Monitor tasks at https://code.earthengine.google.com/tasks.

5.  Download the exported GeoTIFF files from Google Drive and place them in::

        data/raw/landsat/

    The pipeline will find them by pattern matching (year + band name in filename).

By default, the export region is read from::

        data/processed/uhi/ibadan_metropolitan_boundary.gpkg

Use ``--use-bbox`` only when the prepared boundary is not available yet.

Exported bands per year
-----------------------
SR_B2_{year}.tif    — Blue  (surface reflectance, Float32, 0–1)
SR_B3_{year}.tif    — Green
SR_B4_{year}.tif    — Red
SR_B5_{year}.tif    — NIR
SR_B6_{year}.tif    — SWIR-1
ST_B10_{year}.tif   — Surface Temperature raw DN (apply scale factor 0.00341802 + offset 149 → Kelvin)

Notes
-----
•  SR bands are exported as scaled surface reflectance (0–1 Float32).
   The index formulas in compute_urban_indices.py work correctly with these values.

•  ST_B10 is exported as raw Collection-2 DN so that compute_lst.py can apply
   its own scale-factor + offset as expected.

•  Primary dry season = December (previous year) + Jan/Feb/Mar (analysis year).
   To reduce no-data gaps, the exported image can fill missing primary pixels
   from an extended fallback season. This is especially useful for 2015, where
   only Landsat 8 is available and strict cloud filters can remove one path/row.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

LOGGER = logging.getLogger(__name__)

# Fallback bounding box: deliberately wider than the Ibadan metro boundary.
# The old west edge (3.70) clipped out western LGAs such as Ido/Oluyole when
# --use-bbox was used, creating a hard vertical no-data edge in 2015 exports.
# [west, south, east, north]
IBADAN_BBOX: list[float] = [3.45, 7.00, 4.25, 7.90]
DEFAULT_BOUNDARY = Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg")

# GEE collection IDs for Landsat 8 and 9 Collection 2 Level-2
L8_C2 = "LANDSAT/LC08/C02/T1_L2"
L9_C2 = "LANDSAT/LC09/C02/T1_L2"

# SR scale factor and offset (Collection 2 Level-2)
SR_SCALE = 0.0000275
SR_OFFSET = -0.2


# ---------------------------------------------------------------------------
# GEE helper functions
# ---------------------------------------------------------------------------


def _mask_qa(image):
    """Mask clouds and cloud shadows using QA_PIXEL (Collection 2)."""
    import ee
    qa = image.select("QA_PIXEL")
    cloud_bit = 1 << 3        # bit 3 = cloud
    shadow_bit = 1 << 4       # bit 4 = cloud shadow
    dilated_bit = 1 << 1      # bit 1 = dilated cloud
    clear = (
        qa.bitwiseAnd(cloud_bit).eq(0)
        .And(qa.bitwiseAnd(shadow_bit).eq(0))
        .And(qa.bitwiseAnd(dilated_bit).eq(0))
    )
    return image.updateMask(clear)


def _apply_sr_scale(image):
    """Scale SR bands to surface reflectance (0–1) and keep ST_B10 as raw DN."""
    import ee
    sr_bands = image.select("SR_B.").multiply(SR_SCALE).add(SR_OFFSET).clamp(0, 1)
    thermal = image.select("ST_B10")
    return (
        image
        .addBands(sr_bands, overwrite=True)
        .addBands(thermal, overwrite=True)
    )


def _date_range_for_season(year: int, start_month: int, end_month: int) -> tuple[str, str]:
    """Return start/end dates for a season that may cross calendar years.

    If the start month is greater than the end month, the season starts in the
    previous calendar year and ends in the analysis year. The returned end date
    is exclusive, as expected by Earth Engine ``filterDate``.
    """
    if not 1 <= start_month <= 12 or not 1 <= end_month <= 12:
        raise ValueError("Season months must be in the range 1..12.")

    start_year = year - 1 if start_month > end_month else year
    end_year = year
    if end_month == 12:
        exclusive_end_year = end_year + 1
        exclusive_end_month = 1
    else:
        exclusive_end_year = end_year
        exclusive_end_month = end_month + 1
    start = f"{start_year}-{start_month:02d}-01"
    end = f"{exclusive_end_year}-{exclusive_end_month:02d}-01"
    return start, end


def _season_collection(
    year: int,
    region,
    collection_id: str,
    start_month: int,
    end_month: int,
    cloud_cover: float,
):
    """Return a cloud/shadow masked Landsat collection for a seasonal window."""
    import ee
    start, end = _date_range_for_season(year, start_month, end_month)
    return (
        ee.ImageCollection(collection_id)
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", cloud_cover))
        .map(_mask_qa)
    )


def _merged_landsat_collection(
    year: int,
    region,
    start_month: int,
    end_month: int,
    cloud_cover: float,
):
    """Merge Landsat 8 and 9 seasonal collections.

    Landsat 9 only starts in late 2021, so pre-2022 years naturally use only
    Landsat 8. Keeping this helper explicit makes the scene counts easier to
    log and reason about.
    """
    l8 = _season_collection(year, region, L8_C2, start_month, end_month, cloud_cover)
    l9 = _season_collection(year, region, L9_C2, start_month, end_month, cloud_cover)
    return l8.merge(l9)


def _project_path(path: Path) -> Path:
    """Resolve a CLI path relative to the project root."""
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_boundary_region(boundary_path: Path, layer: str | None, simplify_tolerance: float):
    """Read the prepared study-area boundary and return an Earth Engine geometry.

    The boundary is dissolved to one geometry, converted to EPSG:4326, optionally
    simplified, and sent to Earth Engine as GeoJSON. This keeps the export region
    aligned with the actual Ibadan study area instead of using a rectangular bbox.
    """
    import ee
    import geopandas as gpd
    from shapely.geometry import mapping

    resolved = _project_path(boundary_path)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Boundary file not found: {resolved}. Run the study-area preparation script first "
            "or use --use-bbox to export with the fallback rectangular extent."
        )

    read_kwargs = {"layer": layer} if layer else {}
    gdf = gpd.read_file(resolved, **read_kwargs)
    if gdf.empty:
        raise ValueError(f"Boundary layer contains no features: {resolved}")
    if gdf.crs is None:
        raise ValueError(f"Boundary layer has no CRS: {resolved}")

    gdf = gdf.to_crs("EPSG:4326")
    geometry = gdf.geometry.unary_union
    if simplify_tolerance > 0:
        geometry = geometry.simplify(simplify_tolerance, preserve_topology=True)

    if geometry.is_empty:
        raise ValueError(f"Boundary geometry is empty after dissolve: {resolved}")

    geojson = mapping(geometry)
    LOGGER.info("Using study-area boundary from %s", resolved)
    LOGGER.info("Boundary GeoJSON type: %s", geojson.get("type", "unknown"))
    return ee.Geometry(geojson), geojson


def _bbox_region(bbox: list[float]):
    """Return an Earth Engine rectangle and printable GeoJSON for bbox fallback."""
    import ee

    west, south, east, north = bbox
    geojson = {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
        ],
    }
    return ee.Geometry.Rectangle(bbox), geojson


def _submit_export(
    image,
    band: str,
    description: str,
    region,
    scale: int,
    drive_folder: str,
    dry_run: bool,
) -> str:
    """Submit one GEE export task and return its task ID (or 'dry-run')."""
    import ee
    if dry_run:
        return "dry-run"
    task = ee.batch.Export.image.toDrive(
        image=image.select(band).clip(region).toFloat(),
        description=description,
        folder=drive_folder,
        fileNamePrefix=description,
        region=region,
        scale=scale,
        crs="EPSG:4326",          # export in WGS84; pipeline reprojects as needed
        maxPixels=1_000_000_000,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    task.start()
    return task.id


def export_year(
    year: int,
    region,
    drive_folder: str,
    dry_run: bool,
    cloud_cover: float,
    fallback_cloud_cover: float,
    primary_start_month: int,
    primary_end_month: int,
    fallback_start_month: int,
    fallback_end_month: int,
    gap_fill: bool,
) -> dict[str, str]:
    """Create a dry-season median composite for *year* and submit export tasks."""
    import ee

    combined = _merged_landsat_collection(
        year,
        region,
        primary_start_month,
        primary_end_month,
        cloud_cover,
    )

    n_scenes = combined.size().getInfo()
    start, end = _date_range_for_season(year, primary_start_month, primary_end_month)
    LOGGER.info(
        "Year %d primary window %s to %s: %d scenes after cloud filtering (< %.1f%%).",
        year,
        start,
        end,
        n_scenes,
        cloud_cover,
    )
    if n_scenes == 0:
        raise RuntimeError(
            f"No Landsat scenes found for {year} dry season over the study area. "
            "Try increasing --cloud-cover or widening the fallback season."
        )

    composite = combined.map(_apply_sr_scale).median()
    if gap_fill:
        fallback = _merged_landsat_collection(
            year,
            region,
            fallback_start_month,
            fallback_end_month,
            fallback_cloud_cover,
        )
        fallback_n = fallback.size().getInfo()
        fb_start, fb_end = _date_range_for_season(year, fallback_start_month, fallback_end_month)
        LOGGER.info(
            "Year %d fallback window %s to %s: %d scenes after cloud filtering (< %.1f%%).",
            year,
            fb_start,
            fb_end,
            fallback_n,
            fallback_cloud_cover,
        )
        if fallback_n > 0:
            fallback_composite = fallback.map(_apply_sr_scale).median()
            composite = composite.unmask(fallback_composite)
        else:
            LOGGER.warning("Year %d fallback collection is empty; exporting primary composite only.", year)

    band_specs = {
        "SR_B2": (f"SR_B2_{year}", 30),
        "SR_B3": (f"SR_B3_{year}", 30),
        "SR_B4": (f"SR_B4_{year}", 30),
        "SR_B5": (f"SR_B5_{year}", 30),
        "SR_B6": (f"SR_B6_{year}", 30),
        "ST_B10": (f"ST_B10_{year}", 30),  # raw DN — scale applied by compute_lst.py
    }

    tasks = {}
    for band, (description, scale) in band_specs.items():
        task_id = _submit_export(composite, band, description, region, scale, drive_folder, dry_run)
        status = "[dry run]" if dry_run else f"task {task_id}"
        LOGGER.info("  %-20s → %s", description, status)
        tasks[description] = task_id

    return tasks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Landsat 8/9 dry-season composites from Google Earth Engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2015, 2023, 2025],
        help="Analysis years to export (default: 2015 2023 2025).",
    )
    parser.add_argument(
        "--cloud-cover",
        type=float,
        default=60.0,
        help=(
            "Maximum scene-level CLOUD_COVER percentage for the primary dry-season collection "
            "(default: 60). A strict value like 20 can create path/row gaps in 2015."
        ),
    )
    parser.add_argument(
        "--fallback-cloud-cover",
        type=float,
        default=80.0,
        help="Maximum CLOUD_COVER percentage for fallback gap-filling scenes (default: 80).",
    )
    parser.add_argument(
        "--primary-start-month",
        type=int,
        default=12,
        help="Primary season start month. Default is 12 for December of the previous year.",
    )
    parser.add_argument(
        "--primary-end-month",
        type=int,
        default=3,
        help="Primary season end month. Default is 3 for March of the analysis year.",
    )
    parser.add_argument(
        "--fallback-start-month",
        type=int,
        default=11,
        help="Fallback season start month used only to fill primary no-data pixels (default: 11).",
    )
    parser.add_argument(
        "--fallback-end-month",
        type=int,
        default=4,
        help="Fallback season end month used only to fill primary no-data pixels (default: 4).",
    )
    parser.add_argument(
        "--no-gap-fill",
        action="store_true",
        help="Disable fallback seasonal gap filling and export only the primary dry-season median.",
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=IBADAN_BBOX,
        help="Fallback bounding box in WGS84. Used only with --use-bbox.",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=DEFAULT_BOUNDARY,
        help=(
            "Prepared study-area boundary GeoPackage/Shapefile used as the export region "
            f"(default: {DEFAULT_BOUNDARY})."
        ),
    )
    parser.add_argument(
        "--boundary-layer",
        default=None,
        help="Optional layer name when --boundary points to a multi-layer GeoPackage.",
    )
    parser.add_argument(
        "--simplify-tolerance",
        type=float,
        default=0.0001,
        help=(
            "Boundary simplification tolerance in degrees before sending geometry to GEE "
            "(default: 0.0001). Use 0 to disable."
        ),
    )
    parser.add_argument(
        "--use-bbox",
        action="store_true",
        help="Use the fallback rectangular bbox instead of the prepared study-area boundary.",
    )
    parser.add_argument(
        "--drive-folder",
        default="ibadan_heat_risk",
        help="Google Drive folder to export into (created if absent).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be exported without submitting tasks.",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Authenticate with Earth Engine and exit.",
    )
    parser.add_argument(
        "--project",
        default=None,
        metavar="PROJECT_ID",
        help=(
            "Google Cloud Project ID that has the Earth Engine API enabled "
            "(e.g. 'my-ee-project-123').  If omitted, the script tries the "
            "EE_PROJECT / GOOGLE_CLOUD_PROJECT environment variables, then "
            "your saved credentials file, then prompts interactively."
        ),
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help=(
            "Guided first-time setup: authenticate AND resolve your project ID, "
            "then exit.  Run this once before any export."
        ),
    )
    return parser.parse_args()


def _resolve_project(cli_value: str | None) -> str | None:
    """Return a GEE project ID, checking sources in priority order.

    1. ``--project`` CLI argument
    2. ``EE_PROJECT`` environment variable
    3. ``GOOGLE_CLOUD_PROJECT`` environment variable
    4. ``project`` key inside ``~/.config/earthengine/credentials``
    5. Interactive prompt (stdin)

    Returns the project string, or None if the user skips the prompt.
    """
    import json
    import os
    from pathlib import Path

    # 1. CLI
    if cli_value:
        return cli_value.strip()

    # 2 & 3. Environment variables
    for var in ("EE_PROJECT", "GOOGLE_CLOUD_PROJECT"):
        val = os.environ.get(var, "").strip()
        if val:
            LOGGER.info("Using project from env var %s: %s", var, val)
            return val

    # 4. Credentials file (earthengine-api >= 0.1.370 stores project there)
    cred_path = Path.home() / ".config" / "earthengine" / "credentials"
    if cred_path.exists():
        try:
            creds = json.loads(cred_path.read_text())
            project = creds.get("project_id") or creds.get("project", "")
            if project:
                LOGGER.info("Using project from credentials file: %s", project)
                return project.strip()
        except Exception:
            pass

    # 5. Interactive prompt
    print()
    print("─" * 60)
    print("  Earth Engine Project ID required")
    print("─" * 60)
    print()
    print("  The Earth Engine Python API now requires a Google Cloud")
    print("  Project that has the Earth Engine API enabled.")
    print()
    print("  How to find or create your project ID:")
    print("  1. Go to https://console.cloud.google.com")
    print("  2. Select or create a project (free tier is fine)")
    print("  3. Enable the Earth Engine API:")
    print("     https://console.cloud.google.com/apis/library/earthengine.googleapis.com")
    print("  4. Your project ID is shown in the top bar (e.g. 'my-ee-project-123')")
    print()
    print("  TIP: You can skip typing it every time by setting an env var:")
    print("       set EE_PROJECT=your-project-id   (Windows)")
    print("       export EE_PROJECT=your-project-id (Linux/macOS)")
    print()

    try:
        project = input("  Enter your Google Cloud Project ID (or press Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        project = ""

    return project if project else None


def _initialize_ee(project: str | None) -> bool:
    """Authenticate and initialise Earth Engine.  Returns True on success."""
    import ee

    def _init(proj: str | None) -> None:
        if proj:
            ee.Initialize(project=proj)
        else:
            ee.Initialize()

    # Try initialising with saved credentials first
    try:
        _init(project)
        LOGGER.info("Earth Engine initialised successfully (project: %s).", project or "default")
        return True
    except Exception as first_err:
        err_str = str(first_err).lower()

        # If the error is specifically about a missing/invalid project, don't re-auth
        if "no project found" in err_str or "permission_denied" in err_str:
            LOGGER.debug("Init failed (project issue): %s", first_err)
            return False

        # Otherwise credentials may be missing/expired — re-authenticate
        LOGGER.info("Credentials not found or expired — opening browser for authentication.")
        try:
            ee.Authenticate()
            _init(project)
            LOGGER.info("Earth Engine initialised after re-authentication.")
            return True
        except Exception as auth_err:
            print(f"\nERROR: Earth Engine authentication failed: {auth_err}")
            print("Make sure you have a Google account with Earth Engine access.")
            print("Sign up free at https://earthengine.google.com")
            return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    try:
        import ee
    except ImportError:
        print("ERROR: earthengine-api is not installed.")
        print("  pip install earthengine-api geemap")
        return 1

    # ── Guided setup mode ────────────────────────────────────────────────────
    if args.setup:
        print("\nFirst-time setup for Google Earth Engine\n")
        print("Step 1: Authenticate (browser will open) ...")
        try:
            ee.Authenticate()
        except Exception as exc:
            print(f"ERROR: {exc}")
            return 1

        project = _resolve_project(args.project)
        if not project:
            print("\nNo project ID provided. Re-run with --project YOUR_PROJECT_ID")
            return 1

        if not _initialize_ee(project):
            return 1

        print(f"\nSetup complete!  Project: {project}")
        print("\nTo avoid entering the project ID every time, set this environment variable:")
        print(f"  Windows : set EE_PROJECT={project}")
        print(f"  Linux   : export EE_PROJECT={project}")
        print("\nYou can now export Landsat data:")
        print("  python scripts/02a_gee_export_landsat.py --years 2015 2023 2025")
        return 0

    # ── Resolve project ID ───────────────────────────────────────────────────
    project = _resolve_project(args.project)
    if not project:
        print(
            "\nERROR: No Google Cloud Project ID found.\n"
            "Re-run with:  python scripts/02a_gee_export_landsat.py --project YOUR_PROJECT_ID\n"
            "Or run the guided setup:  python scripts/02a_gee_export_landsat.py --setup"
        )
        return 1

    # ── Initialise Earth Engine ──────────────────────────────────────────────
    if not _initialize_ee(project):
        return 1

    if args.auth_only:
        print(f"Authentication successful.  Project: {project}")
        return 0

    # ── Build export region ─────────────────────────────────────────────────
    if args.use_bbox:
        region, region_geojson = _bbox_region(args.bbox)
        region_label = (
            f"fallback bbox W={args.bbox[0]} S={args.bbox[1]} "
            f"E={args.bbox[2]} N={args.bbox[3]}"
        )
        LOGGER.warning("Using fallback bbox export region, not the prepared study-area boundary.")
    else:
        try:
            region, region_geojson = _load_boundary_region(
                args.boundary,
                args.boundary_layer,
                args.simplify_tolerance,
            )
            region_label = str(_project_path(args.boundary))
        except (FileNotFoundError, ValueError) as err:
            print(f"\nERROR: {err}")
            print("\nFix by preparing the boundary first, for example:")
            print("  python scripts/01_prepare_study_area.py --boundary data/raw/boundary/nigeria_lgas.shp")
            print("\nOr explicitly use the rectangular fallback:")
            print("  python scripts/02a_gee_export_landsat.py --use-bbox --years 2023")
            return 1

    # ── Run exports ──────────────────────────────────────────────────────────
    print(f"Project     : {project}")
    print(f"Region      : {region_label}")
    print(f"Region type : {region_geojson.get('type', 'unknown')}")
    print(f"Drive folder: {args.drive_folder}")
    print(f"Years       : {args.years}")
    print(f"Primary    : months {args.primary_start_month}->{args.primary_end_month}, cloud < {args.cloud_cover}%")
    if args.no_gap_fill:
        print("Gap fill    : disabled")
    else:
        print(
            f"Gap fill    : months {args.fallback_start_month}->{args.fallback_end_month}, "
            f"cloud < {args.fallback_cloud_cover}%"
        )
    print()

    all_tasks: dict[str, dict[str, str]] = {}
    for year in args.years:
        print(f"--- {year} ---")
        try:
            all_tasks[str(year)] = export_year(
                year=year,
                region=region,
                drive_folder=args.drive_folder,
                dry_run=args.dry_run,
                cloud_cover=args.cloud_cover,
                fallback_cloud_cover=args.fallback_cloud_cover,
                primary_start_month=args.primary_start_month,
                primary_end_month=args.primary_end_month,
                fallback_start_month=args.fallback_start_month,
                fallback_end_month=args.fallback_end_month,
                gap_fill=not args.no_gap_fill,
            )
        except RuntimeError as err:
            LOGGER.error("%s", err)

    if args.dry_run:
        print("\n[DRY RUN] No tasks were submitted.")
        return 0

    print("\nExport tasks submitted successfully.")
    print("Monitor progress at: https://code.earthengine.google.com/tasks")
    print(f"\nWhen complete, download all GeoTIFF files from Google Drive > {args.drive_folder}/")
    print("and place them in:  data/raw/landsat/")
    print("\nThen run:")
    for year in args.years:
        print(f"  python scripts/02e_clip_landsat_to_boundary.py --years {year}")
        print(f"  python scripts/03_compute_lst.py --year {year} --landsat-dir data/raw/landsat_clipped")
        print(f"  python scripts/04_compute_urban_indices.py --year {year} --landsat-dir data/raw/landsat_clipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
