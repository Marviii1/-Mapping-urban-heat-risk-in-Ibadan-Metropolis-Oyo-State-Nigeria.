"""Export lightweight dashboard assets for GitHub and Streamlit Cloud."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def export_geojson(source: Path, destination: Path) -> Path | None:
    """Export a vector layer to WGS84 GeoJSON if the source exists."""
    if not source.exists():
        print(f"missing: {source}")
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    gdf = gpd.read_file(source).to_crs("EPSG:4326")
    gdf.to_file(destination, driver="GeoJSON")
    print(f"wrote: {destination} ({destination.stat().st_size / 1000:.1f} KB)")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Export lightweight web dashboard assets.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "app" / "assets",
        help="Directory for Streamlit-ready public assets.",
    )
    args = parser.parse_args()

    exports = [
        (
            PROJECT_ROOT / "data" / "processed" / "uhi" / "ibadan_lgas.gpkg",
            args.output_dir / "ibadan_lgas.geojson",
        ),
        (
            PROJECT_ROOT / "data" / "processed" / "uhi" / "ibadan_metropolitan_boundary.gpkg",
            args.output_dir / "ibadan_metropolitan_boundary.geojson",
        ),
    ]
    for source, destination in exports:
        export_geojson(source, destination)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
