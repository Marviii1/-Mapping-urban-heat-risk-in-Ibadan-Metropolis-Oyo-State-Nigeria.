"""Build priority cooling intervention zones from multi-indicator combination.

Logic
-----
A zone is prioritised for urban cooling intervention when it has:

    High LST          — hottest pixels in the city
  + High UHI          — heat caused by urbanisation, not just climate
  + Significant Gi*   — statistically confirmed hot spot cluster
  + High population   — people are actually exposed to the heat
  + Low NDVI          — no natural cooling from vegetation
  + Low adaptive cap. — community has limited capacity to cope

Six indicators are normalised to [0, 1], then combined via a weighted sum
into a composite Priority Score (0 = lowest, 1 = highest).  The score is
classified into four actionable priority tiers.

Priority tiers
--------------
4  Very High — severe heat + high vulnerability → urgent intervention
3  High      — strong UHI + dense population   → tree planting, cool roofs
2  Moderate  — increasing heat risk            → urban planning controls
1  Low       — cooler or well-vegetated        → conserve existing green areas
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape

from src.utils.raster_utils import read_band, write_raster

LOGGER = logging.getLogger(__name__)

# ── Default indicator weights ─────────────────────────────────────────────────
# Must sum to 1.0.  Adjust via config if needed.
DEFAULT_WEIGHTS: dict[str, float] = {
    "lst":               0.20,   # thermal exposure
    "uhi_intensity":     0.20,   # urban-caused heat
    "gistar_zscore":     0.15,   # spatial significance
    "population":        0.15,   # human exposure
    "ndvi_inverted":     0.15,   # vegetation deficit (1 - NDVI_norm)
    "hvi":               0.15,   # composite vulnerability
}

# Priority tier labels and thresholds (applied to the 0–1 composite score)
PRIORITY_TIERS: list[tuple[float, int, str, str]] = [
    # (min_score, code, label, recommended_action)
    (0.75, 4, "Very High", "Urgent: emergency greening + heat-health response plan"),
    (0.50, 3, "High",      "Priority: tree planting, cool roofs, shading infrastructure"),
    (0.25, 2, "Moderate",  "Monitor: urban planning controls, incremental greening"),
    (0.00, 1, "Low",       "Conserve: protect existing green areas and water bodies"),
]

PRIORITY_COLOURS: dict[int, str] = {
    4: "#A50026",
    3: "#F46D43",
    2: "#FEE08B",
    1: "#1A9850",
}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise(arr: np.ndarray) -> np.ndarray:
    """Min-max normalise to [0, 1], preserving NaN."""
    valid = arr[np.isfinite(arr)]
    if valid.size == 0 or valid.max() == valid.min():
        return np.where(np.isfinite(arr), 0.0, np.nan).astype("float32")
    vmin, vmax = float(valid.min()), float(valid.max())
    result = (arr - vmin) / (vmax - vmin)
    result[~np.isfinite(arr)] = np.nan
    return result.astype("float32")


def _load_if_exists(path: Path) -> np.ndarray | None:
    """Return band array or None if the file doesn't exist."""
    if not path.exists():
        LOGGER.warning("Layer not found (skipping): %s", path.name)
        return None
    arr, _ = read_band(path)
    return arr.astype("float32")


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def compute_priority_score(
    input_layers: dict[str, Path],
    weights: dict[str, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Compute a weighted composite priority score.

    Parameters
    ----------
    input_layers:
        Mapping from indicator name → raster path.  Expected keys (any subset):
        ``lst``, ``uhi_intensity``, ``gistar_zscore``, ``population``,
        ``ndvi``, ``hvi``.
        Note: ``ndvi`` is automatically inverted (1 − NDVI_norm) so that low
        vegetation = high priority score.
    weights:
        Optional custom weight dict.  Defaults to ``DEFAULT_WEIGHTS``.

    Returns
    -------
    score:
        Float32 composite score array in [0, 1].
    priority_classes:
        Integer class array {1, 2, 3, 4}.
    diagnostics:
        Dict with per-indicator contribution statistics.
    """
    w = weights or DEFAULT_WEIGHTS

    # Read and normalise each available layer
    normalised: dict[str, np.ndarray] = {}
    profile = None

    for name, path in input_layers.items():
        arr = _load_if_exists(path)
        if arr is None:
            continue
        norm = _normalise(arr)
        if name == "ndvi":
            # Invert NDVI: areas with MORE vegetation get LOWER priority score
            norm = 1.0 - norm
            key = "ndvi_inverted"
        else:
            key = name
        normalised[key] = norm
        if profile is None:
            with rasterio.open(path) as src:
                profile = src.profile.copy()

    if not normalised:
        raise FileNotFoundError(
            "No input raster layers were found. Run the LST, UHI, ESDA, and HVI "
            "pipeline steps first."
        )

    if profile is None:
        raise RuntimeError("Could not read raster profile from any input layer.")

    # Determine grid shape from first available layer
    ref_shape = next(iter(normalised.values())).shape

    # Build weighted composite, normalising weights to available layers
    available_keys = set(normalised.keys())
    active_weights = {k: v for k, v in w.items() if k in available_keys}
    total_w = sum(active_weights.values())
    if total_w == 0:
        raise ValueError("No weights match available layers.")
    if total_w < 0.999:
        LOGGER.warning(
            "Only %.0f%% of expected indicators are available. "
            "Score is normalised to available layers.",
            total_w * 100,
        )

    score = np.zeros(ref_shape, dtype="float32")
    nodata = np.zeros(ref_shape, dtype=bool)

    diagnostics: dict[str, dict] = {}
    for key, arr in normalised.items():
        layer_w = active_weights.get(key, 0.0)
        contribution = arr * (layer_w / total_w)
        score += np.where(np.isfinite(contribution), contribution, 0.0)
        nodata |= ~np.isfinite(arr)
        valid_vals = arr[np.isfinite(arr)]
        diagnostics[key] = {
            "weight_applied": round(layer_w / total_w, 3),
            "mean_normalised": round(float(valid_vals.mean()), 3) if valid_vals.size else np.nan,
        }

    score[nodata] = np.nan

    # Classify into priority tiers
    classes = np.full(ref_shape, np.nan, dtype="float32")
    valid = np.isfinite(score)
    for min_score, code, _, _ in sorted(PRIORITY_TIERS, key=lambda t: t[0]):
        classes[valid & (score >= min_score)] = code

    return score.astype("float32"), classes.astype("float32"), diagnostics


# ---------------------------------------------------------------------------
# Vectorisation
# ---------------------------------------------------------------------------

def vectorize_priority_zones(
    score_array: np.ndarray,
    classes_array: np.ndarray,
    profile: dict,
    boundary_path: Path,
    output_path: Path,
    min_area_ha: float = 5.0,
) -> gpd.GeoDataFrame:
    """Convert priority raster to a clean vector GeoPackage.

    Polygons smaller than *min_area_ha* hectares are removed to avoid noise.

    Parameters
    ----------
    score_array:
        Continuous composite score (0–1).
    classes_array:
        Integer priority class array {1, 2, 3, 4}.
    profile:
        Rasterio profile for the arrays.
    boundary_path:
        Ibadan metro boundary (for CRS reference and clipping).
    output_path:
        Output GeoPackage path.
    min_area_ha:
        Minimum polygon area in hectares to keep.

    Returns
    -------
    GeoDataFrame with priority zone polygons.
    """
    transform = profile["transform"]
    crs = profile.get("crs", "EPSG:32631")
    min_area_m2 = min_area_ha * 10_000

    # Build tier lookup
    tier_lookup = {code: (label, action)
                   for _, code, label, action in PRIORITY_TIERS}

    polygons = []
    for geom_json, val in shapes(
        classes_array.astype("int16"),
        mask=(np.isfinite(classes_array)).astype("uint8"),
        transform=transform,
    ):
        code = int(val)
        if code not in tier_lookup:
            continue
        geom = shape(geom_json)
        if geom.area < min_area_m2:
            continue
        label, action = tier_lookup[code]
        polygons.append({
            "geometry": geom,
            "priority_code": code,
            "priority_label": label,
            "recommended_action": action,
            "hex_colour": PRIORITY_COLOURS.get(code, "#FFFFFF"),
            "area_ha": round(geom.area / 10_000, 2),
        })

    if not polygons:
        raise ValueError(
            "No priority zones were generated. "
            "Check that the input rasters cover the study area."
        )

    gdf = gpd.GeoDataFrame(polygons, crs=crs)
    gdf = gdf.sort_values("priority_code", ascending=False).reset_index(drop=True)

    # Dissolve by priority class for cleaner cartographic output
    dissolved = gdf.dissolve(by="priority_code", aggfunc={
        "priority_label": "first",
        "recommended_action": "first",
        "hex_colour": "first",
        "area_ha": "sum",
    }).reset_index()
    dissolved = dissolved.sort_values("priority_code", ascending=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dissolved.to_file(output_path, layer="priority_cooling_zones", driver="GPKG")

    # Also save undissolved version for detailed analysis
    detail_path = output_path.with_name(output_path.stem + "_detailed.gpkg")
    gdf.to_file(detail_path, layer="priority_zones_detailed", driver="GPKG")

    LOGGER.info("Priority zones saved: %s", output_path)
    LOGGER.info("  %-12s  %8s  %s", "Priority", "Area(ha)", "Recommended Action")
    LOGGER.info("  " + "─" * 70)
    for _, row in dissolved.iterrows():
        LOGGER.info(
            "  %-12s  %8.0f  %s",
            row["priority_label"],
            row["area_ha"],
            row["recommended_action"],
        )

    return dissolved


# ---------------------------------------------------------------------------
# Full pipeline convenience function
# ---------------------------------------------------------------------------

def build_priority_zones(
    input_layers: dict[str, Path],
    boundary_path: Path,
    output_dir: Path,
    year: int,
    weights: dict[str, float] | None = None,
    min_area_ha: float = 5.0,
) -> dict[str, Path]:
    """Run the full priority zone pipeline for one analysis year.

    Parameters
    ----------
    input_layers:
        Dict mapping indicator names to raster paths. Expected keys:
        ``lst``, ``uhi_intensity``, ``gistar_zscore``, ``population``,
        ``ndvi``, ``hvi``.  Missing layers are skipped with a warning.
    boundary_path:
        Ibadan metro boundary GeoPackage.
    output_dir:
        Directory for output files.
    year:
        Analysis year (used in output filenames).
    weights:
        Custom indicator weights dict (optional).
    min_area_ha:
        Minimum polygon area in hectares for vector output.

    Returns
    -------
    Dict with paths to: ``score``, ``classes``, ``vector``, ``summary``.
    """
    import rasterio

    LOGGER.info("Computing priority cooling intervention zones for %d …", year)

    score, classes, diagnostics = compute_priority_score(input_layers, weights)

    # Get profile from first available input layer
    ref_path = next(p for p in input_layers.values() if p.exists())
    with rasterio.open(ref_path) as src:
        profile = src.profile.copy()
        profile.update(dtype="float32", count=1, nodata=-9999.0, compress="deflate")

    output_dir.mkdir(parents=True, exist_ok=True)
    score_path = output_dir / f"priority_score_{year}.tif"
    classes_path = output_dir / f"priority_classes_{year}.tif"
    vector_path = output_dir / f"priority_cooling_zones_{year}.gpkg"

    write_raster(score_path, score, profile)
    write_raster(classes_path, classes, profile)

    gdf = vectorize_priority_zones(
        score, classes, profile, boundary_path, vector_path, min_area_ha
    )

    # Summary CSV
    summary = gdf[["priority_code", "priority_label", "area_ha", "recommended_action"]].copy()
    summary["year"] = year
    summary_path = output_dir / f"priority_zones_summary_{year}.csv"
    summary.to_csv(summary_path, index=False)

    # Diagnostics log
    LOGGER.info("Indicator diagnostics:")
    for key, stats in diagnostics.items():
        LOGGER.info("  %-20s  weight=%.3f  mean=%.3f",
                    key, stats["weight_applied"], stats.get("mean_normalised", np.nan))

    return {
        "score": score_path,
        "classes": classes_path,
        "vector": vector_path,
        "summary": summary_path,
    }
