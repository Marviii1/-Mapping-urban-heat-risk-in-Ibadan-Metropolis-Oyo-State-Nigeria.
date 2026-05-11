"""Import a pre-built Ibadan boundary GeoPackage into the pipeline.

Use this script instead of 01_prepare_study_area.py when you already have a
GeoPackage containing the 11 Ibadan LGA polygons (e.g. exported from QGIS or
ArcGIS) and do not need to filter from a full Nigeria LGA shapefile.

The script:
  1.  Reads the GeoPackage and auto-detects the LGA and State columns.
  2.  Validates that all 11 expected LGAs are present.
  3.  Reprojects from EPSG:4326 → EPSG:32631 (WGS 84 / UTM Zone 31N).
  4.  Computes accurate planar areas in km².
  5.  Tags each LGA as core_urban or peri_urban based on the config.
  6.  Dissolves to a single Ibadan metropolitan boundary polygon.
  7.  Writes all pipeline-expected outputs to data/processed/uhi/ and
      data/processed/tables/.

Outputs
-------
  data/processed/uhi/ibadan_lgas.gpkg
  data/processed/uhi/ibadan_metropolitan_boundary.gpkg
  data/processed/tables/ibadan_lga_list.csv

Usage
-----
  python scripts/01b_import_prebuilt_boundary.py \\
      --gpkg data/raw/boundary/ibadan_lgas.gpkg

  # Specify a layer name if the file has multiple layers:
  python scripts/01b_import_prebuilt_boundary.py \\
      --gpkg data/raw/boundary/ibadan_lgas.gpkg \\
      --layer new_lga_nigeria_2003
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.boundary import (
    detect_lga_column,
    detect_state_column,
    normalize_name,
    _log_match_table,
)
from src.utils.config import ensure_directory, load_yaml, project_path

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_lgas(
    gdf: gpd.GeoDataFrame,
    lga_column: str,
    target_lgas: list[str],
) -> tuple[list[str], list[str]]:
    """Return (matched_source_names, missing_target_names)."""
    target_lookup = {normalize_name(n): n for n in target_lgas}
    found, missing = [], []

    for _, row in gdf.iterrows():
        key = normalize_name(row[lga_column])
        if key in target_lookup:
            found.append(row[lga_column])

    for key, original in target_lookup.items():
        if not any(normalize_name(r[lga_column]) == key for _, r in gdf.iterrows()):
            missing.append(original)

    return found, missing


# ---------------------------------------------------------------------------
# Core import function
# ---------------------------------------------------------------------------

def import_prebuilt_boundary(
    gpkg_path: Path,
    layer: str | None,
    target_lgas: list[str],
    core_lgas: list[str],
    periurban_lgas: list[str],
    projected_crs: str,
    output_dir: Path,
    table_dir: Path,
) -> dict[str, Path]:
    """Read, validate, enrich, and export the pre-built boundary GeoPackage."""

    # ── Read layer ────────────────────────────────────────────────────────────
    available_layers = fiona.listlayers(gpkg_path)
    LOGGER.info("GeoPackage layers: %s", available_layers)

    if layer is None:
        layer = available_layers[0]
        if len(available_layers) > 1:
            LOGGER.warning(
                "Multiple layers found — using '%s'. "
                "Pass --layer to choose a different one.",
                layer,
            )
    elif layer not in available_layers:
        raise ValueError(
            f"Layer '{layer}' not found in {gpkg_path.name}. "
            f"Available layers: {available_layers}"
        )

    gdf = gpd.read_file(gpkg_path, layer=layer)
    LOGGER.info("Read %d features from layer '%s'.", len(gdf), layer)

    if gdf.empty:
        raise ValueError(f"Layer '{layer}' contains no features.")
    if gdf.crs is None:
        raise ValueError(
            "The GeoPackage has no CRS defined. "
            "Set the CRS to EPSG:4326 in QGIS/ArcGIS and re-export."
        )

    LOGGER.info("Source CRS: %s (EPSG:%s)", gdf.crs.name, gdf.crs.to_epsg())

    # ── Detect columns ────────────────────────────────────────────────────────
    lga_column = detect_lga_column(gdf)
    state_column = detect_state_column(gdf)
    LOGGER.info("LGA column   : %s", lga_column)
    LOGGER.info("State column : %s", state_column or "not detected")

    # ── Validate LGA names ────────────────────────────────────────────────────
    found, missing = validate_lgas(gdf, lga_column, target_lgas)

    LOGGER.info("─" * 64)
    LOGGER.info("  LGA validation  (%d expected, %d found)", len(target_lgas), len(found))
    LOGGER.info("─" * 64)

    # Build a pseudo-selected frame to reuse _log_match_table
    target_lookup = {normalize_name(n): n for n in target_lgas}
    working = gdf.copy()
    working["target_lga_name"] = working[lga_column].map(
        lambda v: target_lookup.get(normalize_name(v), "")
    )
    matched = working[working["target_lga_name"] != ""].copy()
    _log_match_table(matched, lga_column, missing)

    if missing:
        LOGGER.warning(
            "%d LGA(s) not found in GeoPackage: %s",
            len(missing), ", ".join(missing),
        )
        LOGGER.warning(
            "The boundary will be built from the %d matched LGAs only. "
            "Check the LGA column ('%s') for spelling differences.",
            len(found), lga_column,
        )
    else:
        LOGGER.info("All %d LGAs matched successfully.", len(target_lgas))

    if matched.empty:
        raise ValueError(
            "No target LGAs found. "
            "Check that the LGA column contains the expected names."
        )

    # ── Reproject ─────────────────────────────────────────────────────────────
    LOGGER.info("Reprojecting to %s …", projected_crs)
    matched = matched.to_crs(projected_crs)

    # ── Enrich ────────────────────────────────────────────────────────────────
    matched["area_sq_km"] = (matched.geometry.area / 1_000_000).round(3)

    core_keys = {normalize_name(n) for n in core_lgas}
    periurban_keys = {normalize_name(n) for n in periurban_lgas}

    def _zone(row: pd.Series) -> str:
        key = normalize_name(row.get("target_lga_name", row[lga_column]))
        if key in core_keys:
            return "core_urban"
        if key in periurban_keys:
            return "peri_urban"
        return "unclassified"

    matched["zone_type"] = matched.apply(_zone, axis=1)

    # ── Dissolve to metro boundary ────────────────────────────────────────────
    dissolved = matched.dissolve().reset_index(drop=True)
    dissolved["name"] = "Ibadan Metropolis"
    dissolved["lga_count"] = len(matched)
    dissolved["area_sq_km"] = (dissolved.geometry.area / 1_000_000).round(3)
    dissolved = dissolved.set_crs(projected_crs, allow_override=True)

    # ── Write outputs ─────────────────────────────────────────────────────────
    output_dir = ensure_directory(output_dir)
    table_dir = ensure_directory(table_dir)

    lgas_path = output_dir / "ibadan_lgas.gpkg"
    boundary_path = output_dir / "ibadan_metropolitan_boundary.gpkg"
    table_path = table_dir / "ibadan_lga_list.csv"

    matched.to_file(lgas_path, layer="ibadan_lgas", driver="GPKG")
    dissolved.to_file(boundary_path, layer="ibadan_metropolitan_boundary", driver="GPKG")

    table = pd.DataFrame({
        "lga_name": matched["target_lga_name"].where(
            matched["target_lga_name"] != "", matched[lga_column]
        ),
        "source_lga_name": matched[lga_column],
        "zone_type": matched["zone_type"],
        "area_sq_km": matched["area_sq_km"],
    }).sort_values("lga_name").reset_index(drop=True)
    table.to_csv(table_path, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    n_core = (matched["zone_type"] == "core_urban").sum()
    n_peri = (matched["zone_type"] == "peri_urban").sum()
    total_area = dissolved["area_sq_km"].iloc[0]

    LOGGER.info("─" * 64)
    LOGGER.info("  Study area ready")
    LOGGER.info("  LGAs         : %d  (%d core urban  |  %d peri-urban)", len(matched), n_core, n_peri)
    LOGGER.info("  Total area   : %.1f km²", total_area)
    LOGGER.info("  Output CRS   : %s", projected_crs)
    LOGGER.info("─" * 64)

    return {
        "lgas": lgas_path,
        "boundary": boundary_path,
        "table": table_path,
        "missing_lgas": missing,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a pre-built Ibadan boundary GeoPackage into the pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--gpkg",
        type=Path,
        default=Path("data/raw/boundary/ibadan_lgas.gpkg"),
        help="Path to the pre-built boundary GeoPackage (default: data/raw/boundary/ibadan_lgas.gpkg).",
    )
    parser.add_argument(
        "--layer",
        default=None,
        help=(
            "Layer name to read from the GeoPackage. "
            "If omitted, the first layer is used."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/project_config.yml"),
        help="Project YAML configuration path.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    cfg = load_yaml(args.config)
    gpkg = args.gpkg if args.gpkg.is_absolute() else project_path(args.gpkg)

    if not gpkg.exists():
        print(f"ERROR: GeoPackage not found: {gpkg}")
        print("Place your boundary GeoPackage at data/raw/boundary/ibadan_lgas.gpkg")
        print("or pass the path with --gpkg path/to/your_boundary.gpkg")
        return 1

    sa = cfg["study_area"]

    try:
        outputs = import_prebuilt_boundary(
            gpkg_path=gpkg,
            layer=args.layer,
            target_lgas=sa["target_lgas"],
            core_lgas=sa.get("core_lgas", []),
            periurban_lgas=sa.get("periurban_lgas", []),
            projected_crs=cfg["project"]["crs_projected"],
            output_dir=project_path("data/processed/uhi"),
            table_dir=project_path("data/processed/tables"),
        )
    except (ValueError, FileNotFoundError) as exc:
        LOGGER.error("%s", exc)
        return 1

    print("\nStudy area import complete.")
    print(f"  LGAs GeoPackage : {outputs['lgas']}")
    print(f"  Metro boundary  : {outputs['boundary']}")
    print(f"  LGA table CSV   : {outputs['table']}")
    if outputs["missing_lgas"]:
        print(f"\n  WARNING — {len(outputs['missing_lgas'])} LGA(s) not matched:")
        for name in outputs["missing_lgas"]:
            print(f"    ✗ {name}")
        print("\n  Re-run 01_prepare_study_area.py --list-lgas to see exact shapefile names.")

    print("\nNext steps:")
    print("  1. Authenticate GEE    :  python scripts/02a_gee_export_landsat.py --setup")
    print("  2. Prepare ancillary   :  make data")
    print("  3. Compute LST         :  make lst")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
