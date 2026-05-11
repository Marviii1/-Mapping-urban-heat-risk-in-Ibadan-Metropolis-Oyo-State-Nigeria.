"""Prepare GHSL built-up surface density for Ibadan.

This script prepares a GHSL GHS-BUILT-S raster for GWR/HVI modelling.

It supports three workflows:

1. Automatic global ZIP download from the JRC GHSL open-data server.
2. Manual ZIP/TIF placed in ``data/raw/ghsl/`` with ``--skip-download``.
3. Direct local file path with ``--input-raster``.

The output is always:

    data/processed/vulnerability/built_up_density_{year}.tif

Examples
--------
    python scripts/02c_prepare_ghsl.py --year 2023
    python scripts/02c_prepare_ghsl.py --year 2023 --skip-download
    python scripts/02c_prepare_ghsl.py --year 2023 --input-raster data/raw/ghsl/GHS_BUILT_S_E2020.tif
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import rasterio
from rasterio.merge import merge

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocess import (
    clip_raster_to_boundary,
    download_file,
    extract_zip,
    reproject_raster,
)
from src.utils.config import load_yaml, project_path

LOGGER = logging.getLogger(__name__)


GHSL_GLOBAL_URLS: dict[int, str] = {
    2015: (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2015_GLOBE_R2023A_54009_100/"
        "V1-0/GHS_BUILT_S_E2015_GLOBE_R2023A_54009_100_V1_0.zip"
    ),
    2020: (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100/"
        "V1-0/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0.zip"
    ),
    # Use 2020 as the built-up proxy for 2023 unless a user supplies another raster.
    2023: (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100/"
        "V1-0/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0.zip"
    ),
    2025: (
        "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        "GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_100/"
        "V1-0/GHS_BUILT_S_E2025_GLOBE_R2023A_54009_100_V1_0.zip"
    ),
}


def nearest_ghsl_url(year: int) -> tuple[str, int]:
    """Return the best configured GHSL URL and actual data year."""
    if year in GHSL_GLOBAL_URLS:
        return GHSL_GLOBAL_URLS[year], year
    available = sorted(GHSL_GLOBAL_URLS)
    nearest = min(available, key=lambda item: abs(item - year))
    LOGGER.warning("No GHSL URL configured for %d. Using %d as proxy.", year, nearest)
    return GHSL_GLOBAL_URLS[nearest], nearest


def extract_and_mosaic(
    zips: list[Path],
    extract_dir: Path,
    output_path: Path,
    nodata: float = -9999.0,
) -> Path:
    """Extract TIF files from ZIPs, mosaic them if needed, and save a GeoTIFF."""
    tifs: list[Path] = []
    for zip_path in zips:
        extracted = extract_zip(zip_path, extract_dir / zip_path.stem)
        tifs.extend(path for path in extracted if path.suffix.lower() in {".tif", ".tiff"})

    if not tifs:
        raise FileNotFoundError("No GeoTIFF files found inside the GHSL ZIP file(s).")

    if len(tifs) == 1:
        return tifs[0]

    LOGGER.info("Mosaicking %d GHSL rasters -> %s", len(tifs), output_path)
    datasets = [rasterio.open(path) for path in tifs]
    try:
        mosaic_array, transform = merge(datasets, nodata=nodata)
        profile = datasets[0].profile.copy()
        profile.update(
            height=mosaic_array.shape[1],
            width=mosaic_array.shape[2],
            transform=transform,
            nodata=nodata,
            compress="deflate",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(mosaic_array)
    finally:
        for dataset in datasets:
            dataset.close()
    return output_path


def source_to_tif(source_path: Path, temp_dir: Path) -> Path:
    """Return a usable GeoTIFF from a local GHSL TIF/TIFF/ZIP source."""
    suffix = source_path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        return source_path
    if suffix == ".zip":
        return extract_and_mosaic([source_path], temp_dir / "extracted", temp_dir / "ghsl_mosaic.tif")
    raise ValueError(f"Unsupported GHSL source format: {source_path}")


def choose_manual_source(raw_dir: Path) -> Path:
    """Pick the first manually supplied GHSL TIF/ZIP in raw_dir."""
    candidates = sorted(raw_dir.glob("GHS_BUILT_S_*.tif"))
    candidates += sorted(raw_dir.glob("GHS_BUILT_S_*.tiff"))
    candidates += sorted(raw_dir.glob("GHS_BUILT_S_*.zip"))
    if not candidates:
        raise FileNotFoundError(
            f"No GHSL TIF/TIFF/ZIP files found in {raw_dir}. "
            "Place a downloaded GHSL file there or run without --skip-download."
        )
    return candidates[0]


def prepare_ghsl(
    year: int,
    boundary_path: Path,
    raw_dir: Path,
    output_dir: Path,
    projected_crs: str = "EPSG:32631",
    skip_download: bool = False,
    input_raster: Path | None = None,
) -> Path:
    """Prepare GHSL built-up density from download or local source."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)

        if input_raster is not None:
            source_path = input_raster
            if not source_path.exists():
                raise FileNotFoundError(f"GHSL input raster not found: {source_path}")
            LOGGER.info("Using local GHSL source: %s", source_path)
        elif skip_download:
            source_path = choose_manual_source(raw_dir)
            LOGGER.info("Using manually supplied GHSL source: %s", source_path)
        else:
            url, data_year = nearest_ghsl_url(year)
            source_path = raw_dir / Path(url).name
            download_file(url, source_path)
            if data_year != year:
                LOGGER.warning("GHSL %d is used as proxy for %d.", data_year, year)

        source_tif = source_to_tif(source_path, temp_dir)
        reproj_path = temp_dir / "ghsl_reprojected.tif"
        reproject_raster(source_tif, reproj_path, projected_crs)

        output_path = output_dir / f"built_up_density_{year}.tif"
        clip_raster_to_boundary(reproj_path, boundary_path, output_path)

    LOGGER.info("Built-up density raster saved: %s", output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare GHSL built-up density for Ibadan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--input-raster",
        type=Path,
        default=None,
        help="Existing GHSL TIF/TIFF/ZIP to clip/reproject instead of downloading.",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg"),
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use a manually downloaded GHSL TIF/TIFF/ZIP in data/raw/ghsl/.",
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

    cfg = load_yaml(args.config)
    boundary = args.boundary if args.boundary.is_absolute() else project_path(args.boundary)
    input_raster = (
        args.input_raster
        if args.input_raster is None or args.input_raster.is_absolute()
        else project_path(args.input_raster)
    )

    if not boundary.exists():
        print(f"ERROR: Boundary not found: {boundary}")
        print("Run scripts/01_prepare_study_area.py or scripts/01b_import_prebuilt_boundary.py first.")
        return 1

    try:
        output = prepare_ghsl(
            year=args.year,
            boundary_path=boundary,
            raw_dir=project_path("data/raw/ghsl"),
            output_dir=project_path("data/processed/vulnerability"),
            projected_crs=cfg["project"]["crs_projected"],
            skip_download=args.skip_download,
            input_raster=input_raster,
        )
        print(f"Built-up density raster saved: {output}")
        print("\nNOTE: GHSL built-up surface may be used as a proxy for nearby analysis years.")
    except Exception as exc:
        LOGGER.error("GHSL preparation failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
