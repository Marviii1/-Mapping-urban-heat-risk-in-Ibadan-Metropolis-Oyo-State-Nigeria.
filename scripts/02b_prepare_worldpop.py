"""Download and prepare WorldPop population density rasters for Ibadan.

WorldPop provides gridded population estimates for Nigeria at 100 m resolution.
This script:

  1. Downloads the appropriate Nigeria population raster from the WorldPop Hub
     (https://www.worldpop.org).
  2. Clips it to the Ibadan metropolitan boundary.
  3. Reprojects it to EPSG:32631 (WGS 84 / UTM Zone 31N).
  4. Saves it as ``data/processed/vulnerability/population_density_{year}.tif``.

For years without a direct WorldPop release the nearest available year is used
as a proxy (see WORLDPOP_URLS below).

Usage
-----
    python scripts/02b_prepare_worldpop.py --year 2023
    python scripts/02b_prepare_worldpop.py --year 2023 --input-raster data/raw/worldpop/my_population.tif
    python scripts/02b_prepare_worldpop.py --year 2020
    python scripts/02b_prepare_worldpop.py --year 2015
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocess import clip_and_reproject_raster, download_file
from src.utils.config import load_yaml, project_path

LOGGER = logging.getLogger(__name__)

# WorldPop constrained individual countries UN-adjusted datasets (100 m)
# https://www.worldpop.org/datacollection/NGA
WORLDPOP_URLS: dict[int, str] = {
    2015: (
        "https://data.worldpop.org/GIS/Population/"
        "Global_2000_2020/2015/NGA/nga_ppp_2015.tif"
    ),
    2020: (
        "https://data.worldpop.org/GIS/Population/"
        "Global_2000_2020/2020/NGA/nga_ppp_2020.tif"
    ),
    # WorldPop annual series ends at 2020; use 2020 as proxy for 2023
    2023: (
        "https://data.worldpop.org/GIS/Population/"
        "Global_2000_2020/2020/NGA/nga_ppp_2020.tif"
    ),
}


def _nearest_url(year: int) -> tuple[str, int]:
    """Return the best available WorldPop URL and the actual data year."""
    if year in WORLDPOP_URLS:
        return WORLDPOP_URLS[year], year
    available = sorted(WORLDPOP_URLS.keys())
    nearest = min(available, key=lambda y: abs(y - year))
    LOGGER.warning(
        "No WorldPop URL for year %d. Using %d data as proxy.", year, nearest
    )
    return WORLDPOP_URLS[nearest], nearest


def prepare_worldpop(
    year: int,
    boundary_path: Path,
    raw_dir: Path,
    output_dir: Path,
    projected_crs: str = "EPSG:32631",
) -> Path:
    """Download, clip, and reproject the WorldPop raster for *year*."""
    url, data_year = _nearest_url(year)
    raw_file = raw_dir / f"nga_ppp_{data_year}.tif"

    # Download if not already present
    download_file(url, raw_file)

    # Clip + reproject
    output_path = output_dir / f"population_density_{year}.tif"
    clip_and_reproject_raster(raw_file, boundary_path, output_path, projected_crs)

    LOGGER.info("Population density raster saved: %s", output_path)
    if data_year != year:
        LOGGER.warning(
            "NOTE: Population data is from %d (used as proxy for %d). "
            "Update WORLDPOP_URLS in this script when a newer release is available.",
            data_year,
            year,
        )
    return output_path


def prepare_local_population_raster(
    input_raster: Path,
    year: int,
    boundary_path: Path,
    output_dir: Path,
    projected_crs: str = "EPSG:32631",
) -> Path:
    """Clip/reproject a user-supplied population raster for GWR/HVI."""
    if not input_raster.exists():
        raise FileNotFoundError(f"Population raster not found: {input_raster}")

    output_path = output_dir / f"population_density_{year}.tif"
    clip_and_reproject_raster(input_raster, boundary_path, output_path, projected_crs)
    LOGGER.info("Local population raster prepared: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and prepare WorldPop population density for Ibadan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--year", type=int, required=True, help="Analysis year (e.g. 2023).")
    parser.add_argument(
        "--input-raster",
        type=Path,
        default=None,
        help=(
            "Use an existing local population raster instead of downloading WorldPop. "
            "The raster will be clipped/reprojected and saved as "
            "data/processed/vulnerability/population_density_{year}.tif."
        ),
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg"),
        help="Ibadan metropolitan boundary GeoPackage.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/project_config.yml"),
        help="Project config YAML path.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    cfg = load_yaml(args.config)
    boundary = args.boundary if args.boundary.is_absolute() else project_path(args.boundary)

    if not boundary.exists():
        print(f"ERROR: Boundary file not found: {boundary}")
        print("Run scripts/01_prepare_study_area.py --boundary <nigeria_lgas.shp> first.")
        return 1

    raw_dir = project_path("data/raw/worldpop")
    output_dir = project_path("data/processed/vulnerability")
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.input_raster is not None:
            input_raster = (
                args.input_raster
                if args.input_raster.is_absolute()
                else project_path(args.input_raster)
            )
            output = prepare_local_population_raster(
                input_raster=input_raster,
                year=args.year,
                boundary_path=boundary,
                output_dir=output_dir,
                projected_crs=cfg["project"]["crs_projected"],
            )
        else:
            output = prepare_worldpop(
                year=args.year,
                boundary_path=boundary,
                raw_dir=raw_dir,
                output_dir=output_dir,
                projected_crs=cfg["project"]["crs_projected"],
            )
        print(f"Population density raster saved: {output}")
    except Exception as exc:
        LOGGER.error("WorldPop preparation failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
