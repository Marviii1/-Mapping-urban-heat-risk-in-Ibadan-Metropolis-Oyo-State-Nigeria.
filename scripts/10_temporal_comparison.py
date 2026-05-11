"""Multi-year temporal comparison of heat indicators across Ibadan.

Computes per-pixel change maps, Mann-Kendall trend direction, and LGA-level
summary tables comparing 2015, 2020, and 2023 (or any available subset).

Outputs
-------
data/processed/temporal/
    lst_change_2015_2020.tif          — LST delta (°C)
    lst_change_2020_2023.tif
    lst_change_2015_2023.tif          — full period change
    ndvi_change_2015_2020.tif
    ndvi_change_2020_2023.tif
    ndvi_change_2015_2023.tif
    lst_trend_tau.tif                 — Mann-Kendall Tau (–1 to +1)
    lst_trend_slope_per_year.tif      — linear trend slope (°C / year)
    ndvi_trend_tau.tif
    ndvi_trend_slope_per_year.tif

data/processed/tables/
    temporal_lga_summary.csv          — LGA-level means per year + change

Usage
-----
    python scripts/10_temporal_comparison.py
    python scripts/10_temporal_comparison.py --years 2020 2023
    python scripts/10_temporal_comparison.py --variable ndvi
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.cartography import save_continuous_raster_map
from src.utils.config import load_yaml, project_path
from src.utils.raster_utils import read_band, write_raster

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

VARIABLE_PATHS: dict[str, str] = {
    "lst":  "data/processed/lst/lst_ibadan_{year}_celsius.tif",
    "ndvi": "data/processed/indices/ndvi_{year}.tif",
    "ndbi": "data/processed/indices/ndbi_{year}.tif",
    "uhi":  "data/processed/uhi/uhi_intensity_{year}.tif",
}

VARIABLE_TITLES: dict[str, str] = {
    "lst": "Land Surface Temperature",
    "ndvi": "Normalized Difference Vegetation Index",
    "ndbi": "Normalized Difference Built-up Index",
    "uhi": "Urban Heat Island Intensity",
}

VARIABLE_LABELS: dict[str, str] = {
    "lst": "Change in LST (deg C)",
    "ndvi": "Change in NDVI",
    "ndbi": "Change in NDBI",
    "uhi": "Change in UHI intensity (deg C)",
}

BOUNDARY_PATH = project_path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg")


def find_available_years(variable: str, candidate_years: list[int]) -> list[int]:
    """Return years for which a processed raster actually exists on disk."""
    available = []
    for year in candidate_years:
        path = project_path(VARIABLE_PATHS[variable].format(year=year))
        if path.exists():
            available.append(year)
        else:
            LOGGER.warning("Not found (skipping): %s", path)
    return sorted(available)


def read_as_reference_grid(path: Path, reference_path: Path) -> tuple[np.ndarray, dict]:
    """Read a raster, resampling it to the reference grid when needed."""
    with rasterio.open(reference_path) as ref:
        ref_profile = ref.profile.copy()
        ref_transform = ref.transform
        ref_crs = ref.crs
        ref_shape = (ref.height, ref.width)

    with rasterio.open(path) as src:
        array = src.read(1).astype("float32")
        if src.nodata is not None:
            array[array == src.nodata] = np.nan

        same_grid = (
            src.crs == ref_crs
            and src.transform == ref_transform
            and src.height == ref_shape[0]
            and src.width == ref_shape[1]
        )
        if same_grid:
            return array, ref_profile

        LOGGER.info("Aligning %s to reference grid %s", path.name, reference_path.name)
        destination = np.full(ref_shape, np.nan, dtype="float32")
        reproject(
            source=array,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        return destination, ref_profile


# ---------------------------------------------------------------------------
# Change maps
# ---------------------------------------------------------------------------

def compute_change_map(
    early_path: Path,
    late_path: Path,
    output_path: Path,
) -> Path:
    """Compute late − early pixel-wise change and write to *output_path*."""
    early, profile = read_band(early_path)
    late, _ = read_as_reference_grid(late_path, early_path)

    delta = (late - early).astype("float32")
    delta[~np.isfinite(early) | ~np.isfinite(late)] = np.nan

    profile.update(dtype="float32", nodata=-9999.0, compress="deflate")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_raster(output_path, delta, profile)
    LOGGER.info("Change map: %s  (mean Δ = %.3f)", output_path.name, np.nanmean(delta))
    return output_path


def save_temporal_png(
    raster_path: Path,
    output_path: Path,
    title: str,
    legend_label: str,
    *,
    cmap: str = "RdBu_r",
    symmetric: bool = True,
    limits: tuple[float, float] | None = None,
) -> Path | None:
    """Save a cartographic PNG for a temporal raster if inputs exist."""
    if not raster_path.exists():
        LOGGER.warning("Cannot map missing raster: %s", raster_path)
        return None
    if not BOUNDARY_PATH.exists():
        LOGGER.warning("Cannot map temporal raster; boundary missing: %s", BOUNDARY_PATH)
        return None

    vmin = vmax = None
    if limits is not None:
        vmin, vmax = limits
    elif symmetric:
        array, _ = read_band(raster_path)
        valid = array[np.isfinite(array)]
        if valid.size:
            vabs = float(np.nanpercentile(np.abs(valid), 98))
            if not np.isfinite(vabs) or vabs == 0:
                max_abs = np.nanmax(np.abs(valid))
                vabs = float(max_abs) if np.isfinite(max_abs) and max_abs != 0 else 1.0
            vmin, vmax = -vabs, vabs

    return save_continuous_raster_map(
        raster_path=raster_path,
        output_path=output_path,
        title=title,
        legend_label=legend_label,
        cmap=cmap,
        boundary_path=BOUNDARY_PATH,
        vmin=vmin,
        vmax=vmax,
    )


# ---------------------------------------------------------------------------
# Mann-Kendall trend  (vectorised, works for any n ≥ 3)
# ---------------------------------------------------------------------------

def _mk_vectorised(arrays: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised Mann-Kendall Tau and Z-score for a pixel stack.

    For n time points, computes S = Σ sign(x_j − x_i) for all j > i pairs,
    then Tau = S / (n*(n-1)/2).  A normal approximation gives the Z-score.

    With only 3 time points the test has very low power; Tau is still useful
    as a trend direction indicator (+1 = monotonically warming / greening).

    Parameters
    ----------
    arrays:
        List of n 2-D float arrays ordered earliest → latest.

    Returns
    -------
    tau:
        Kendall's Tau in [−1, +1].  NaN where data is missing.
    z_score:
        Standard normal Z-score (can be used for p-value if n ≥ 8).
    """
    n = len(arrays)
    shape = arrays[0].shape

    s = np.zeros(shape, dtype="float32")
    for i in range(n):
        for j in range(i + 1, n):
            diff = arrays[j].astype("float32") - arrays[i].astype("float32")
            s += np.sign(diff).astype("float32")

    n_pairs = n * (n - 1) / 2.0
    tau = (s / n_pairs).astype("float32")

    # Variance of S under H₀ (no ties assumed)
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    std_s = float(np.sqrt(var_s))

    # Continuity-corrected Z
    z = np.where(s > 0, (s - 1) / std_s,
        np.where(s < 0, (s + 1) / std_s, 0.0)).astype("float32")

    # Apply nodata mask
    nodata = np.zeros(shape, dtype=bool)
    for arr in arrays:
        nodata |= ~np.isfinite(arr)
    tau[nodata] = np.nan
    z[nodata] = np.nan

    return tau, z


def _linear_trend_slope(arrays: list[np.ndarray], years: list[int]) -> np.ndarray:
    """Pixel-wise linear trend slope (units per year) via least-squares.

    Parameters
    ----------
    arrays:
        List of n 2-D float arrays aligned spatially.
    years:
        Corresponding calendar years (same length as *arrays*).

    Returns
    -------
    slope:
        Float32 array of trend slope in [variable units] per year.
    """
    x = np.array(years, dtype="float32")
    x -= x.mean()  # centre for numerical stability
    x_ss = float((x ** 2).sum())

    shape = arrays[0].shape
    slope = np.zeros(shape, dtype="float32")
    nodata = np.zeros(shape, dtype=bool)

    for arr in arrays:
        nodata |= ~np.isfinite(arr)

    for i, (arr, xi) in enumerate(zip(arrays, x)):
        slope += arr.astype("float32") * xi

    slope /= x_ss
    slope[nodata] = np.nan
    return slope


# ---------------------------------------------------------------------------
# LGA-level summary
# ---------------------------------------------------------------------------

def _rasterise_lgas(lgas_path: Path, ref_path: Path) -> tuple[np.ndarray, dict[int, str]]:
    """Rasterise LGA polygons onto the reference raster grid.

    Returns an integer array (LGA code) and a code → name mapping.
    """
    with rasterio.open(ref_path) as src:
        profile = src.profile
        transform = src.transform
        height, width = src.height, src.width
        crs = src.crs

    lgas = gpd.read_file(lgas_path).to_crs(crs)
    lgas["_code"] = range(1, len(lgas) + 1)
    code_to_name = dict(zip(lgas["_code"], lgas.get("LGA", lgas.iloc[:, 0])))

    lga_raster = rasterize(
        [(row.geometry.__geo_interface__, row["_code"]) for _, row in lgas.iterrows()],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="int16",
    )
    return lga_raster, code_to_name


def build_lga_summary(
    variable: str,
    years: list[int],
    lgas_path: Path,
) -> pd.DataFrame:
    """LGA-level mean values per year plus change statistics.

    Returns a DataFrame with LGA names as rows and years as columns,
    plus change columns for each consecutive pair.
    """
    paths = {y: project_path(VARIABLE_PATHS[variable].format(year=y)) for y in years}
    ref_path = next(p for p in paths.values() if p.exists())

    lga_raster, code_to_name = _rasterise_lgas(lgas_path, ref_path)

    records: dict[str, dict] = {name: {} for name in code_to_name.values()}

    for year in years:
        path = paths[year]
        if not path.exists():
            continue
        arr, _ = read_band(path)
        for code, name in code_to_name.items():
            mask = (lga_raster == code) & np.isfinite(arr)
            records[name][f"mean_{year}"] = round(float(arr[mask].mean()), 3) if mask.any() else np.nan

    df = pd.DataFrame.from_dict(records, orient="index")
    df.index.name = "lga_name"

    # Add change columns for consecutive year pairs
    for i in range(len(years) - 1):
        y_early, y_late = years[i], years[i + 1]
        c_early = f"mean_{y_early}"
        c_late = f"mean_{y_late}"
        if c_early in df.columns and c_late in df.columns:
            df[f"change_{y_early}_{y_late}"] = (df[c_late] - df[c_early]).round(3)

    # Full-period change
    if len(years) >= 2 and f"mean_{years[0]}" in df.columns and f"mean_{years[-1]}" in df.columns:
        df[f"change_{years[0]}_{years[-1]}_total"] = (
            df[f"mean_{years[-1]}"] - df[f"mean_{years[0]}"]
        ).round(3)

    return df.reset_index().sort_values("lga_name")


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_temporal_comparison(
    variable: str,
    years: list[int],
    lgas_path: Path,
    output_dir: Path,
    table_dir: Path,
    maps_dir: Path,
    outputs_table_dir: Path,
) -> dict[str, list[Path]]:
    """Run the complete temporal comparison for one variable."""
    available = find_available_years(variable, years)

    if len(available) < 2:
        LOGGER.warning(
            "Only %d year(s) available for '%s'. "
            "Need at least 2 to compute change maps. "
            "Run the LST/indices pipeline for more years first.",
            len(available), variable,
        )
        return {}

    paths = {y: project_path(VARIABLE_PATHS[variable].format(year=y)) for y in available}
    reference_path = paths[available[0]]
    arrays = {y: read_as_reference_grid(paths[y], reference_path)[0].astype("float32") for y in available}
    _, ref_profile = read_band(paths[available[0]])
    ref_profile.update(dtype="float32", nodata=-9999.0, compress="deflate")

    output_dir.mkdir(parents=True, exist_ok=True)
    maps_dir.mkdir(parents=True, exist_ok=True)
    output_files: dict[str, list[Path]] = {
        "change_maps": [],
        "trend": [],
        "tables": [],
        "cartographic_maps": [],
    }

    # ── Change maps ───────────────────────────────────────────────────────────
    for i in range(len(available) - 1):
        y_early, y_late = available[i], available[i + 1]
        change_path = output_dir / f"{variable}_change_{y_early}_{y_late}.tif"
        compute_change_map(paths[y_early], paths[y_late], change_path)
        output_files["change_maps"].append(change_path)
        png_path = maps_dir / f"{variable}_change_{y_early}_{y_late}.png"
        mapped = save_temporal_png(
            raster_path=change_path,
            output_path=png_path,
            title=f"{VARIABLE_TITLES[variable]} Change ({y_early} to {y_late})",
            legend_label=VARIABLE_LABELS[variable],
        )
        if mapped:
            output_files["cartographic_maps"].append(mapped)

    # Full period change
    if len(available) >= 3:
        full_path = output_dir / f"{variable}_change_{available[0]}_{available[-1]}.tif"
        compute_change_map(paths[available[0]], paths[available[-1]], full_path)
        output_files["change_maps"].append(full_path)
        png_path = maps_dir / f"{variable}_change_{available[0]}_{available[-1]}.png"
        mapped = save_temporal_png(
            raster_path=full_path,
            output_path=png_path,
            title=f"{VARIABLE_TITLES[variable]} Overall Change ({available[0]} to {available[-1]})",
            legend_label=VARIABLE_LABELS[variable],
        )
        if mapped:
            output_files["cartographic_maps"].append(mapped)

    # ── Trend analysis ────────────────────────────────────────────────────────
    arr_stack = [arrays[y] for y in available]

    tau, z = _mk_vectorised(arr_stack)
    slope = _linear_trend_slope(arr_stack, available)

    tau_path = output_dir / f"{variable}_trend_tau.tif"
    slope_path = output_dir / f"{variable}_trend_slope_per_year.tif"
    write_raster(tau_path, tau, ref_profile)
    write_raster(slope_path, slope, ref_profile)
    output_files["trend"] = [tau_path, slope_path]
    tau_png = save_temporal_png(
        raster_path=tau_path,
        output_path=maps_dir / f"{variable}_trend_tau.png",
        title=f"{VARIABLE_TITLES[variable]} Mann-Kendall Trend Direction",
        legend_label="Kendall's Tau (-1 decreasing, +1 increasing)",
        limits=(-1, 1),
    )
    if tau_png:
        output_files["cartographic_maps"].append(tau_png)
    slope_png = save_temporal_png(
        raster_path=slope_path,
        output_path=maps_dir / f"{variable}_trend_slope_per_year.png",
        title=f"{VARIABLE_TITLES[variable]} Linear Trend Slope",
        legend_label=f"{VARIABLE_TITLES[variable]} units per year",
    )
    if slope_png:
        output_files["cartographic_maps"].append(slope_png)

    # Trend statistics summary
    valid_tau = tau[np.isfinite(tau)]
    valid_slope = slope[np.isfinite(slope)]
    LOGGER.info("─" * 60)
    LOGGER.info("Trend summary for '%s' (%s)", variable, " → ".join(str(y) for y in available))
    LOGGER.info("  Tau  : mean=%.3f  positive=%.1f%%  negative=%.1f%%",
                float(np.nanmean(valid_tau)),
                float((valid_tau > 0).mean() * 100),
                float((valid_tau < 0).mean() * 100))
    LOGGER.info("  Slope: mean=%.4f units/yr  max=%.4f  min=%.4f",
                float(valid_slope.mean()), float(valid_slope.max()), float(valid_slope.min()))
    if len(available) < 8:
        LOGGER.warning(
            "  NOTE: With only %d time points, Mann-Kendall Tau indicates trend "
            "direction but p-values are not reliable. Tau = ±1 means a perfectly "
            "monotonic trend across all available years.", len(available)
        )
    LOGGER.info("─" * 60)

    # ── LGA-level summary table ───────────────────────────────────────────────
    if lgas_path.exists():
        lga_df = build_lga_summary(variable, available, lgas_path)
        table_dir.mkdir(parents=True, exist_ok=True)
        table_path = table_dir / f"temporal_lga_summary_{variable}.csv"
        lga_df.to_csv(table_path, index=False)
        outputs_table_dir.mkdir(parents=True, exist_ok=True)
        public_table_path = outputs_table_dir / f"temporal_lga_summary_{variable}.csv"
        lga_df.to_csv(public_table_path, index=False)
        LOGGER.info("LGA summary table → %s", table_path)
        output_files["tables"].extend([table_path, public_table_path])
    else:
        LOGGER.warning("LGA GeoPackage not found; skipping LGA summary: %s", lgas_path)

    return output_files


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-year temporal comparison of Ibadan heat indicators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2015, 2023, 2025],
        help="Analysis years (default: 2015 2023 2025).",
    )
    parser.add_argument(
        "--variable",
        choices=list(VARIABLE_PATHS.keys()) + ["all"],
        default="all",
        help="Variable to analyse (default: all).",
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

    lgas_path = project_path("data/processed/uhi/ibadan_lgas.gpkg")
    output_dir = project_path("data/processed/temporal")
    table_dir = project_path("data/processed/tables")
    maps_dir = project_path("outputs/maps")
    outputs_table_dir = project_path("outputs/tables")

    variables = list(VARIABLE_PATHS.keys()) if args.variable == "all" else [args.variable]

    all_outputs: dict[str, dict] = {}
    for var in variables:
        print(f"\n── {var.upper()} ──")
        outputs = run_temporal_comparison(
            variable=var,
            years=args.years,
            lgas_path=lgas_path,
            output_dir=output_dir,
            table_dir=table_dir,
            maps_dir=maps_dir,
            outputs_table_dir=outputs_table_dir,
        )
        all_outputs[var] = outputs
        for category, file_list in outputs.items():
            for f in file_list:
                print(f"  {category:<12} {f}")

    if not any(all_outputs.values()):
        print(
            "\nNo outputs generated. Make sure you have run the LST and indices "
            "pipeline for at least two years:\n"
            "  make lst   (for each year)\n"
            "  make indices   (for each year)"
        )
        return 1

    print(f"\nAll outputs written to: {output_dir}")
    print(f"LGA summary tables  : {table_dir}")
    print(f"Cartographic maps   : {maps_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
