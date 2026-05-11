"""Prepare OSM-derived distance-to-green-space and distance-to-water rasters.

This script uses OSMnx to download park/vegetation and water body features for
the Ibadan metropolitan area, rasterizes them onto a 100 m grid aligned to the
Ibadan boundary, then computes Euclidean distance transforms to produce:

    data/processed/vulnerability/distance_to_green_space_{year}.tif
    data/processed/vulnerability/distance_to_water_{year}.tif

Both outputs are in EPSG:32631, units = metres, clipped to the Ibadan boundary.

A higher distance value = farther from cooling infrastructure = higher
vulnerability (lower adaptive capacity).

OSM feature categories
----------------------
Green spaces:
  leisure   = park, garden, nature_reserve, recreation_ground, golf_course
  natural   = wood, forest, grassland, scrub, heath, meadow
  landuse   = forest, grass, meadow, village_green, recreation_ground

Water bodies:
  natural   = water, bay
  waterway  = river, stream, canal, drain, ditch
  landuse   = reservoir, basin

Usage
-----
    python scripts/02d_prepare_osm_layers.py --year 2023
    python scripts/02d_prepare_osm_layers.py --year 2023 --resolution 100
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocess import clip_raster_to_boundary
from src.utils.config import load_yaml, project_path
from src.utils.raster_utils import write_raster

LOGGER = logging.getLogger(__name__)

# OSM tag queries
GREEN_SPACE_TAGS: dict[str, Any] = {
    "leisure": ["park", "garden", "nature_reserve", "recreation_ground", "golf_course"],
    "natural": ["wood", "forest", "grassland", "scrub", "heath", "meadow"],
    "landuse": ["forest", "grass", "meadow", "village_green", "recreation_ground"],
}

WATER_TAGS: dict[str, Any] = {
    "natural": ["water", "bay"],
    "waterway": ["river", "stream", "canal", "drain", "ditch"],
    "landuse": ["reservoir", "basin"],
}

# Minimum geometry area in square metres to keep (removes tiny artefacts)
MIN_AREA_SQM = 1_000.0


# ---------------------------------------------------------------------------
# OSM download
# ---------------------------------------------------------------------------


def _fetch_osm_features(
    boundary: gpd.GeoDataFrame,
    tags: dict[str, Any],
    label: str,
    buffer_m: float = 500.0,
) -> gpd.GeoDataFrame | None:
    """Fetch OSM features within a slightly-buffered Ibadan boundary.

    Returns a GeoDataFrame in EPSG:32631 or None if no features were found.
    """
    try:
        import osmnx as ox
    except ImportError:
        raise ImportError("osmnx is required. Run: pip install osmnx")

    # Buffer by a small margin so features just outside the boundary are caught
    boundary_wgs84 = boundary.to_crs("EPSG:4326")
    union_poly = boundary_wgs84.union_all() if hasattr(boundary_wgs84, "union_all") else boundary_wgs84.unary_union
    buffered = union_poly.buffer(buffer_m / 111_320)  # rough degrees from metres

    LOGGER.info("Fetching OSM %s features ...", label)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            gdf = ox.features_from_polygon(buffered, tags=tags)
        except Exception as exc:
            LOGGER.warning("OSMnx query for %s returned no features: %s", label, exc)
            return None

    if gdf.empty:
        LOGGER.warning("No OSM %s features found in the study area.", label)
        return None

    # Keep only polygon/multipolygon geometries (discard lines and points)
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf = gdf.to_crs("EPSG:32631")
    gdf = gdf[gdf.geometry.area >= MIN_AREA_SQM].copy()
    LOGGER.info("  %d %s polygons after filtering.", len(gdf), label)
    return gdf


# ---------------------------------------------------------------------------
# Rasterization and distance transform
# ---------------------------------------------------------------------------


def _make_reference_profile(
    boundary: gpd.GeoDataFrame,
    resolution_m: float,
) -> dict:
    """Build a rasterio profile for a grid aligned to the boundary."""
    boundary_proj = boundary.to_crs("EPSG:32631")
    minx, miny, maxx, maxy = boundary_proj.total_bounds
    width = int(np.ceil((maxx - minx) / resolution_m))
    height = int(np.ceil((maxy - miny) / resolution_m))
    transform = from_bounds(minx, miny, maxx, maxy, width, height)
    return {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "crs": "EPSG:32631",
        "transform": transform,
        "width": width,
        "height": height,
        "nodata": -9999.0,
        "compress": "deflate",
    }


def _rasterize_features(
    features: gpd.GeoDataFrame | None,
    profile: dict,
) -> np.ndarray:
    """Rasterize polygon features; returns a binary uint8 array (1 = feature)."""
    shape = (profile["height"], profile["width"])
    if features is None or features.empty:
        return np.zeros(shape, dtype="uint8")

    geoms = [
        (geom, 1)
        for geom in features.geometry
        if geom is not None and not geom.is_empty
    ]
    if not geoms:
        return np.zeros(shape, dtype="uint8")

    burned = rasterize(
        geoms,
        out_shape=shape,
        transform=profile["transform"],
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    return burned


def _distance_raster(
    binary: np.ndarray,
    resolution_m: float,
    nodata_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Compute Euclidean distance (metres) from every pixel to nearest feature.

    Pixels already inside a feature have distance 0.
    *nodata_mask* marks pixels outside the study area (set to NaN in output).
    """
    # distance_transform_edt computes distance FROM background (0) TO nearest foreground (1)
    inverted = (binary == 0).astype("uint8")
    distance_pixels = distance_transform_edt(inverted)
    distance_metres = (distance_pixels * resolution_m).astype("float32")

    if nodata_mask is not None:
        distance_metres[nodata_mask] = np.nan

    return distance_metres


def _study_area_mask(boundary: gpd.GeoDataFrame, profile: dict) -> np.ndarray:
    """Return a boolean mask (True = outside study area) for nodata assignment."""
    geoms = [(g.__geo_interface__, 1) for g in boundary.geometry if g is not None]
    inside = rasterize(
        geoms,
        out_shape=(profile["height"], profile["width"]),
        transform=profile["transform"],
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    return inside == 0  # True where outside


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def prepare_osm_layers(
    year: int,
    boundary_path: Path,
    output_dir: Path,
    resolution_m: float = 100.0,
) -> dict[str, Path]:
    """Full OSM pipeline for one analysis year. Returns output file paths."""
    boundary = gpd.read_file(boundary_path)
    if boundary.crs is None or boundary.crs.to_epsg() != 32631:
        boundary = boundary.to_crs("EPSG:32631")

    profile = _make_reference_profile(boundary, resolution_m)
    outside_mask = _study_area_mask(boundary, profile)

    # --- Green spaces ---
    green_gdf = _fetch_osm_features(boundary, GREEN_SPACE_TAGS, "green space")
    green_binary = _rasterize_features(green_gdf, profile)
    green_distance = _distance_raster(green_binary, resolution_m, outside_mask)

    # --- Water bodies ---
    water_gdf = _fetch_osm_features(boundary, WATER_TAGS, "water body")
    water_binary = _rasterize_features(water_gdf, profile)
    water_distance = _distance_raster(water_binary, resolution_m, outside_mask)

    # --- Save ---
    output_dir.mkdir(parents=True, exist_ok=True)

    green_out = output_dir / f"distance_to_green_space_{year}.tif"
    water_out = output_dir / f"distance_to_water_{year}.tif"

    write_raster(green_out, green_distance, profile)
    write_raster(water_out, water_distance, profile)

    LOGGER.info("Green space distance raster → %s", green_out)
    LOGGER.info("Water distance raster       → %s", water_out)

    # Diagnostic summary
    valid = ~outside_mask
    if valid.any():
        for name, arr in [("Green space dist", green_distance), ("Water dist", water_distance)]:
            vals = arr[valid & np.isfinite(arr)]
            if vals.size:
                LOGGER.info(
                    "  %s: min=%.0f m, median=%.0f m, max=%.0f m",
                    name,
                    vals.min(),
                    np.median(vals),
                    vals.max(),
                )

    return {"distance_to_green_space": green_out, "distance_to_water": water_out}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare OSM green space and water distance rasters for Ibadan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg"),
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=100.0,
        metavar="METRES",
        help="Output grid resolution in metres (default: 100).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/project_config.yml"),
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    boundary = args.boundary if args.boundary.is_absolute() else project_path(args.boundary)
    if not boundary.exists():
        print(f"ERROR: Boundary not found: {boundary}")
        print("Run scripts/01_prepare_study_area.py first.")
        return 1

    output_dir = project_path("data/processed/vulnerability")

    try:
        outputs = prepare_osm_layers(
            year=args.year,
            boundary_path=boundary,
            output_dir=output_dir,
            resolution_m=args.resolution,
        )
        for name, path in outputs.items():
            print(f"{name}: {path}")
    except Exception as exc:
        LOGGER.error("OSM layer preparation failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
