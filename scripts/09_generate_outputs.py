"""Generate final cartographic outputs, reports, tables, and dashboard catalog.

This script is intended as the final publication step after LST, indices, UHI,
ESDA, GWR, and HVI have been executed.

Outputs
-------
outputs/maps/
    Publication-style PNG maps with legends, boundary overlay, north arrow,
    scale bar, and source notes.

outputs/tables/
    Web/report-ready copies of important CSV tables.

outputs/reports/
    Markdown and PDF summary reports.

outputs/catalog/
    CSV/JSON file catalog used by the Streamlit dashboard and GitHub README.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.cartography import (
    raster_stats,
    save_class_raster_map,
    save_continuous_raster_map,
    save_vector_category_map,
    write_pdf_report,
)
from src.utils.config import project_path

LOGGER = logging.getLogger(__name__)


BOUNDARY = project_path("data/processed/uhi/ibadan_metropolitan_boundary.gpkg")
LGAS = project_path("data/processed/uhi/ibadan_lgas.gpkg")


RASTER_SPECS = {
    "lst": {
        "path": "data/processed/lst/lst_ibadan_{year}_celsius.tif",
        "title": "Land Surface Temperature",
        "legend": "LST (deg C)",
        "cmap": "inferno",
    },
    "uhi": {
        "path": "data/processed/uhi/uhi_intensity_{year}.tif",
        "title": "Urban Heat Island Intensity",
        "legend": "UHI intensity (deg C above rural reference)",
        "cmap": "YlOrRd",
    },
    "ndvi": {
        "path": "data/processed/indices/ndvi_{year}.tif",
        "title": "Normalized Difference Vegetation Index",
        "legend": "NDVI",
        "cmap": "RdYlGn",
    },
    "ndbi": {
        "path": "data/processed/indices/ndbi_{year}.tif",
        "title": "Normalized Difference Built-up Index",
        "legend": "NDBI",
        "cmap": "OrRd",
    },
    "hvi": {
        "path": "data/processed/vulnerability/heat_vulnerability_index_{year}.tif",
        "title": "Heat Vulnerability Index",
        "legend": "HVI score (0-1)",
        "cmap": "magma_r",
    },
    "heat_exposure": {
        "path": "data/processed/vulnerability/heat_exposure_index_{year}.tif",
        "title": "Heat Exposure Index",
        "legend": "Exposure index (0-1)",
        "cmap": "YlOrRd",
    },
    "sensitivity": {
        "path": "data/processed/vulnerability/sensitivity_index_{year}.tif",
        "title": "Sensitivity Index",
        "legend": "Sensitivity index (0-1)",
        "cmap": "Purples",
    },
    "adaptive_capacity": {
        "path": "data/processed/vulnerability/adaptive_capacity_index_{year}.tif",
        "title": "Adaptive Capacity Index",
        "legend": "Adaptive capacity index (0-1)",
        "cmap": "Greens",
    },
}

CLASS_RASTER_SPECS = {
    "uhi_classes": {
        "path": "data/processed/uhi/uhi_classes_{year}.tif",
        "title": "UHI Thermal Stress Classes",
        "classes": {
            1: ("Very Low", "#2166AC"),
            2: ("Low", "#92C5DE"),
            3: ("Moderate", "#FEE08B"),
            4: ("High", "#F46D43"),
            5: ("Very High", "#A50026"),
        },
    }
}

VECTOR_SPECS = {
    "lisa_clusters": {
        "path": "data/processed/esda/lisa_clusters_{year}.gpkg",
        "title": "LISA Cluster Map",
        "column": "lisa_cluster",
        "colors": {
            "High-High": "#d7191c",
            "Low-Low": "#2c7bb6",
            "High-Low": "#fdae61",
            "Low-High": "#abd9e9",
            "Not significant": "#cccccc",
        },
    },
    "gistar_hotspots": {
        "path": "data/processed/esda/gistar_hotspots_{year}.gpkg",
        "title": "Getis-Ord Gi* Hot Spot Map",
        "column": "gistar_cluster",
        "colors": {
            "Hot spot": "#d7191c",
            "Cold spot": "#2c7bb6",
            "Not significant": "#cccccc",
        },
    },
}

GWR_VECTOR_SPEC = {
    "path": "data/processed/gwr/gwr_results_{year}.gpkg",
    "columns": {
        "gwr_local_r2": ("local_r2", "GWR Local R2", "Local R2"),
        "gwr_coef_ndvi": ("coef_ndvi", "GWR Local Coefficient: NDVI", "NDVI coefficient"),
        "gwr_coef_ndbi": ("coef_ndbi", "GWR Local Coefficient: NDBI", "NDBI coefficient"),
        "gwr_coef_built_up_density": (
            "coef_built_up_density",
            "GWR Local Coefficient: Built-up Density",
            "Built-up density coefficient",
        ),
    },
}


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def lga_zonal_table(year: int, raster_path: Path, value_name: str, output_path: Path) -> Path | None:
    if not raster_path.exists() or not LGAS.exists():
        return None
    lgas = gpd.read_file(LGAS)
    with rasterio.open(raster_path) as src:
        lgas_stats = lgas.to_crs(src.crs)
    stats = zonal_stats(lgas_stats, raster_path, stats=["min", "mean", "max", "std"], nodata=-9999)
    records = []
    name_col = "target_lga_name" if "target_lga_name" in lgas.columns else "lga_name"
    for idx, row in lgas.iterrows():
        values = stats[idx]
        records.append(
            {
                "year": year,
                "lga_name": row.get(name_col, row.get("LGA", idx)),
                "zone_type": row.get("zone_type", ""),
                f"{value_name}_min": values.get("min"),
                f"{value_name}_mean": values.get("mean"),
                f"{value_name}_max": values.get("max"),
                f"{value_name}_std": values.get("std"),
            }
        )
    df = pd.DataFrame(records).sort_values(f"{value_name}_mean", ascending=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def make_gwr_maps(year: int, maps_dir: Path, catalog: list[dict]) -> dict[str, Path]:
    path = project_path(GWR_VECTOR_SPEC["path"].format(year=year))
    saved = {}
    if not path.exists():
        return saved
    gdf = gpd.read_file(path)
    for key, (column, title, label) in GWR_VECTOR_SPEC["columns"].items():
        if column not in gdf.columns:
            continue
        output = maps_dir / f"{key}_{year}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        fig_ax = gdf.plot(
            column=column,
            cmap="viridis" if column == "local_r2" else "coolwarm",
            legend=True,
            figsize=(9, 8),
            edgecolor="none",
            legend_kwds={"label": label, "shrink": 0.7},
        )
        ax = fig_ax
        if BOUNDARY.exists():
            gpd.read_file(BOUNDARY).to_crs(gdf.crs).boundary.plot(ax=ax, color="black", linewidth=0.7)
        ax.set_title(f"{title} ({year})", fontsize=14, fontweight="bold")
        ax.set_xlabel("Easting")
        ax.set_ylabel("Northing")
        ax.grid(alpha=0.2, linewidth=0.4)
        fig = ax.figure
        fig.tight_layout()
        fig.savefig(output, dpi=220, bbox_inches="tight")
        import matplotlib.pyplot as plt

        plt.close(fig)
        saved[key] = output
        catalog.append(catalog_record(year, "map", key, output, f"{title} PNG map"))
    return saved


def catalog_record(year: int, kind: str, name: str, path: Path, description: str) -> dict:
    exists = path.exists()
    rel = path.relative_to(PROJECT_ROOT).as_posix() if path.is_absolute() else path.as_posix()
    return {
        "year": year,
        "kind": kind,
        "name": name,
        "path": rel,
        "exists": exists,
        "description": description,
        "size_mb": round(path.stat().st_size / 1_000_000, 3) if exists else None,
    }


def build_catalog(year: int, generated_maps: dict[str, Path], generated_tables: dict[str, Path], reports: dict[str, Path]) -> list[dict]:
    catalog = []
    for name, path in generated_maps.items():
        catalog.append(catalog_record(year, "map", name, path, f"{name.replace('_', ' ').title()} cartographic map"))
    for name, path in generated_tables.items():
        catalog.append(catalog_record(year, "table", name, path, f"{name.replace('_', ' ').title()} table"))
    for name, path in reports.items():
        catalog.append(catalog_record(year, "report", name, path, f"{name.upper()} report"))

    important_sources = {
        "ibadan_lgas": LGAS,
        "ibadan_boundary": BOUNDARY,
        "gwr_results": project_path(f"data/processed/gwr/gwr_results_{year}.gpkg"),
        "lisa_clusters": project_path(f"data/processed/esda/lisa_clusters_{year}.gpkg"),
        "gistar_hotspots": project_path(f"data/processed/esda/gistar_hotspots_{year}.gpkg"),
        "hvi_raster": project_path(f"data/processed/vulnerability/heat_vulnerability_index_{year}.tif"),
        "hvi_ranking": project_path(f"data/processed/tables/ibadan_hvi_ranking_{year}.csv"),
        "gwr_summary": project_path(f"data/processed/gwr/gwr_summary_{year}.txt"),
        "global_ols_summary": project_path(f"data/processed/gwr/gwr_global_ols_summary_{year}.txt"),
    }
    for name, path in important_sources.items():
        catalog.append(catalog_record(year, "source", name, path, f"Source analysis file: {name}"))
    return catalog


def write_markdown_report(
    year: int,
    stats: dict[str, dict[str, float]],
    tables: dict[str, Path],
    maps: dict[str, Path],
    output_path: Path,
) -> Path:
    lines = [
        f"# Ibadan Urban Heat Risk Summary Report ({year})",
        "",
        "## Methodology Conceptualisation",
        "",
        "- Landsat-derived LST provides the thermal exposure surface.",
        "- NDVI, NDBI, and GHSL built-up density represent urban biophysical heat drivers.",
        "- UHI intensity measures the thermal departure from rural reference pixels.",
        "- ESDA identifies global spatial autocorrelation, LISA clusters, and Gi* hot/cold spots.",
        "- GWR models spatially varying relationships between LST and heat drivers.",
        "- HVI combines exposure, sensitivity, and low adaptive capacity using AHP-style weights.",
        "",
        "## Key Raster Statistics",
        "",
        "| Layer | Min | Mean | Max | Std |",
        "|---|---:|---:|---:|---:|",
    ]
    for layer, values in stats.items():
        lines.append(
            f"| {layer} | {values.get('min', np.nan):.3f} | {values.get('mean', np.nan):.3f} | "
            f"{values.get('max', np.nan):.3f} | {values.get('std', np.nan):.3f} |"
        )
    lines.extend(["", "## Generated Maps", "", "| Map | File |", "|---|---|"])
    for name, path in maps.items():
        lines.append(f"| {name.replace('_', ' ').title()} | `{path.relative_to(PROJECT_ROOT).as_posix()}` |")
    lines.extend(["", "## Generated Tables", "", "| Table | File |", "|---|---|"])
    for name, path in tables.items():
        lines.append(f"| {name.replace('_', ' ').title()} | `{path.relative_to(PROJECT_ROOT).as_posix()}` |")
    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- High LST and positive UHI indicate areas of strong heat exposure.",
            "- High-High LISA and Gi* hot spots are statistically meaningful heat clusters.",
            "- Negative NDVI coefficients in GWR support vegetation cooling effects.",
            "- Positive NDBI and built-up density coefficients support urban surface warming effects.",
            "- High HVI zones should be prioritised for greening, shade, cool roofs, and heat-health planning.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def generate_outputs(year: int, skip_maps: bool = False) -> None:
    maps_dir = project_path("outputs/maps")
    tables_dir = project_path("outputs/tables")
    reports_dir = project_path("outputs/reports")
    catalog_dir = project_path("outputs/catalog")
    for directory in (maps_dir, tables_dir, reports_dir, catalog_dir):
        directory.mkdir(parents=True, exist_ok=True)

    maps: dict[str, Path] = {}
    tables: dict[str, Path] = {}
    report_paths: dict[str, Path] = {}
    stats: dict[str, dict[str, float]] = {}
    catalog: list[dict] = []

    if not skip_maps:
        for name, spec in RASTER_SPECS.items():
            raster = project_path(spec["path"].format(year=year))
            if not raster.exists():
                continue
            output = maps_dir / f"{name}_{year}.png"
            save_continuous_raster_map(
                raster,
                output,
                f"{spec['title']} ({year})",
                spec["legend"],
                spec["cmap"],
                BOUNDARY,
            )
            maps[name] = output
            stats[spec["title"]] = raster_stats(raster)

        for name, spec in CLASS_RASTER_SPECS.items():
            raster = project_path(spec["path"].format(year=year))
            if not raster.exists():
                continue
            output = maps_dir / f"{name}_{year}.png"
            save_class_raster_map(raster, output, f"{spec['title']} ({year})", spec["classes"], BOUNDARY)
            maps[name] = output

        for name, spec in VECTOR_SPECS.items():
            vector = project_path(spec["path"].format(year=year))
            if not vector.exists():
                continue
            output = maps_dir / f"{name}_{year}.png"
            save_vector_category_map(
                vector,
                output,
                f"{spec['title']} ({year})",
                spec["column"],
                spec["colors"],
                BOUNDARY,
            )
            maps[name] = output

        maps.update(make_gwr_maps(year, maps_dir, catalog))

    lst_table = lga_zonal_table(
        year,
        project_path(f"data/processed/lst/lst_ibadan_{year}_celsius.tif"),
        "lst_celsius",
        project_path(f"data/processed/tables/lga_lst_summary_{year}.csv"),
    )
    hvi_table = lga_zonal_table(
        year,
        project_path(f"data/processed/vulnerability/heat_vulnerability_index_{year}.tif"),
        "hvi",
        project_path(f"data/processed/tables/lga_hvi_summary_{year}.csv"),
    )

    candidate_tables = {
        "lga_lst_summary": lst_table,
        "lga_hvi_summary": hvi_table,
        "hvi_ranking": project_path(f"data/processed/tables/ibadan_hvi_ranking_{year}.csv"),
        "morans_i": project_path(f"data/processed/esda/morans_i_{year}.csv"),
        "gwr_correlations": project_path(f"data/processed/gwr/gwr_input_correlations_{year}.csv"),
        "gwr_vif": project_path(f"data/processed/gwr/gwr_input_vif_{year}.csv"),
        "gwr_ols_coefficients": project_path(f"data/processed/gwr/gwr_global_ols_coefficients_{year}.csv"),
    }
    for name, source in candidate_tables.items():
        if source and Path(source).exists():
            destination = tables_dir / Path(source).name
            copy_if_exists(Path(source), destination)
            tables[name] = destination

    markdown_report = write_markdown_report(
        year,
        stats,
        tables,
        maps,
        reports_dir / f"ibadan_heat_risk_summary_{year}.md",
    )
    report_paths["markdown"] = markdown_report

    pdf_report = write_pdf_report(
        reports_dir / f"ibadan_heat_risk_summary_{year}.pdf",
        year,
        stats,
        tables,
        maps,
        methodology_notes=[
            "Landsat dry-season LST is used as the thermal exposure baseline.",
            "NDVI, NDBI, and GHSL built-up density are used as heat-driver indicators.",
            "Moran's I, LISA, and Getis-Ord Gi* identify spatial clustering of heat.",
            "GWR uses a 500 m grid and forced adaptive bandwidth for stable local modelling.",
            "HVI combines exposure, sensitivity, and adaptive capacity indicators.",
            "OSM green/water distance layers are treated as static adaptive-capacity proxies.",
        ],
        interpretation_notes=[
            "Higher LST, UHI, HVI, and hot-spot membership indicate priority heat-risk zones.",
            "Negative NDVI coefficients imply vegetation cooling effects.",
            "Positive NDBI and built-up density coefficients imply urban surface warming effects.",
            "LGA rankings support planning prioritisation but should be validated locally.",
        ],
    )
    report_paths["pdf"] = pdf_report

    catalog.extend(build_catalog(year, maps, tables, report_paths))
    catalog_df = pd.DataFrame(catalog).drop_duplicates(subset=["year", "kind", "name", "path"])
    catalog_csv = catalog_dir / f"output_catalog_{year}.csv"
    catalog_json = catalog_dir / f"output_catalog_{year}.json"
    catalog_df.to_csv(catalog_csv, index=False)
    catalog_json.write_text(json.dumps(catalog_df.to_dict(orient="records"), indent=2), encoding="utf-8")

    print(f"\nGenerated outputs for {year}")
    print(f"Maps: {len(maps)}")
    print(f"Tables: {len(tables)}")
    print(f"Markdown report: {markdown_report}")
    print(f"PDF report: {pdf_report}")
    print(f"Output catalog: {catalog_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final maps, tables, PDF report, and dashboard catalog.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--skip-maps", action="store_true")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    generate_outputs(args.year, args.skip_maps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
