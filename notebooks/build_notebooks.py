from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK_DIR = Path(__file__).resolve().parent


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.strip().splitlines(True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.strip().splitlines(True),
    }


def nb(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "gis_env", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


SETUP = """
from pathlib import Path
import sys

cwd = Path.cwd()
if (cwd / "notebook_helpers.py").exists():
    sys.path.insert(0, str(cwd))
elif (cwd / "notebooks" / "notebook_helpers.py").exists():
    sys.path.insert(0, str(cwd / "notebooks"))
else:
    raise FileNotFoundError("Could not find notebook_helpers.py. Run this notebook from the project root or notebooks folder.")

from notebook_helpers import (
    PROJECT_ROOT,
    add_project_root_to_path,
    command_string,
    find_files,
    load_yaml_config,
    notebook_metadata,
    path_status,
    plot_raster,
    print_path_status,
    project_path,
    raster_info,
    raster_stats,
    read_vector,
    run_command,
)

add_project_root_to_path()
RUN_COMMANDS = False  # Change to True only when you want notebook cells to execute CLI scripts.
YEAR = 2023
notebook_metadata("NOTEBOOK_TITLE", YEAR)
"""


NOTEBOOKS: dict[str, list[dict]] = {
    "01_project_overview.ipynb": [
        md(
            """
            # 01 Project Overview

            This notebook is the orientation layer for the Ibadan Urban Heat Risk Intelligence System.
            It checks the project configuration, explains the pipeline order, and confirms which datasets
            already exist before you run heavier geospatial processing.
            """
        ),
        code(SETUP.replace("NOTEBOOK_TITLE", "Project Overview")),
        md("## Step 1 - Load the project configuration\n\nThe main project settings live in `config/project_config.yml`."),
        code(
            """
            config = load_yaml_config("config/project_config.yml")
            config
            """
        ),
        md("## Step 2 - Review the target LGAs\n\nThese are the core and peri-urban LGAs used to define Ibadan Metropolis."),
        code(
            """
            import pandas as pd

            target_lgas = config["study_area"]["target_lgas"]
            pd.DataFrame({"target_lga": target_lgas})
            """
        ),
        md("## Step 3 - Check important project paths\n\nThis tells you what has already been generated and what still needs to be prepared."),
        code(
            """
            import pandas as pd

            important_paths = {
                "raw Nigeria LGA boundary": "data/raw/boundary/nigeria_lgas.shp",
                "prepared Ibadan LGAs": "data/processed/uhi/ibadan_lgas.gpkg",
                "prepared metro boundary": "data/processed/uhi/ibadan_metropolitan_boundary.gpkg",
                "LST raster": f"data/processed/lst/lst_ibadan_{YEAR}_celsius.tif",
                "NDVI raster": f"data/processed/indices/ndvi_{YEAR}.tif",
                "UHI raster": f"data/processed/uhi/uhi_intensity_{YEAR}.tif",
                "LISA clusters": f"data/processed/esda/lisa_clusters_{YEAR}.gpkg",
                "GWR results": f"data/processed/gwr/gwr_results_{YEAR}.gpkg",
                "HVI raster": f"data/processed/vulnerability/heat_vulnerability_index_{YEAR}.tif",
            }
            pd.DataFrame(path_status(important_paths))
            """
        ),
        md("## Step 4 - Run or preview the dependency check\n\nThe notebook defaults to dry-run mode. Set `RUN_COMMANDS = True` in the setup cell to execute."),
        code(
            """
            run_command(["python", "scripts/00_check_dependencies.py"], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 5 - Pipeline command map\n\nUse this table as a reproducible execution guide."),
        code(
            """
            commands = [
                ("Dependency check", "python scripts/00_check_dependencies.py"),
                ("Prepare study area", "python scripts/01_prepare_study_area.py --boundary data/raw/boundary/nigeria_lgas.shp"),
                ("Alternative prebuilt boundary import", "python scripts/01b_import_prebuilt_boundary.py --gpkg data/raw/boundary/ibadan_lgas.gpkg"),
                ("GEE Landsat export", "python scripts/02a_gee_export_landsat.py --years 2015 2020 2023"),
                ("Validate Landsat inputs", f"python scripts/02_download_or_prepare_satellite_data.py --year {YEAR}"),
                ("Compute LST", f"python scripts/03_compute_lst.py --year {YEAR}"),
                ("Compute indices", f"python scripts/04_compute_urban_indices.py --year {YEAR}"),
                ("Compute UHI", f"python scripts/05_compute_uhi_intensity.py --year {YEAR} --reference auto"),
                ("Run ESDA", f"python scripts/06_run_esda.py --target lst --year {YEAR}"),
                ("Run GWR", f"python scripts/07_run_gwr.py --year {YEAR} --dependent lst --predictors ndvi ndbi population_density built_up_density"),
                ("Build HVI", f"python scripts/08_build_vulnerability_index.py --weights config/ahp_weights.yml --year {YEAR}"),
                ("Generate outputs", f"python scripts/09_generate_outputs.py --year {YEAR}"),
                ("Temporal comparison", "python scripts/10_temporal_comparison.py"),
            ]
            pd.DataFrame(commands, columns=["stage", "command"])
            """
        ),
        md("## Step 6 - Inspect prepared boundary when available"),
        code(
            """
            boundary_path = project_path("data/processed/uhi/ibadan_lgas.gpkg")
            if boundary_path.exists():
                lgas = read_vector(boundary_path)
                display(lgas.head())
                print(lgas.crs)
                ax = lgas.plot(figsize=(8, 8), edgecolor="black", alpha=0.6)
                ax.set_title("Prepared Ibadan LGAs")
                ax.set_axis_off()
            else:
                print("Prepared boundary is not available yet. Run the study area preparation script first.")
            """
        ),
    ],
    "02_lst_retrieval_exploration.ipynb": [
        md(
            """
            # 02 LST Retrieval and Exploration

            This notebook guides Landsat 8/9 Collection 2 Level-2 preparation and LST computation.
            It does not force Earth Engine authentication or downloads; it previews commands and validates
            local files before processing.
            """
        ),
        code(SETUP.replace("NOTEBOOK_TITLE", "LST Retrieval Exploration")),
        md("## Step 1 - Understand the required Landsat bands\n\nFor LST, the pipeline needs `ST_B10`. For later indices, it also needs `SR_B2`, `SR_B3`, `SR_B4`, `SR_B5`, and `SR_B6`."),
        code(
            """
            landsat_files = find_files("data/raw/landsat", [f"*{YEAR}*.tif", f"*{YEAR}*.TIF"])
            print(f"Found {len(landsat_files)} Landsat GeoTIFF file(s) for {YEAR}.")
            for path in landsat_files[:30]:
                print(path.relative_to(PROJECT_ROOT))
            """
        ),
        md("## Step 2 - Preview Earth Engine export commands\n\nRun authentication once, then export dry-season composites. Keep `RUN_COMMANDS = False` until you are ready."),
        code(
            """
            run_command(["python", "scripts/02a_gee_export_landsat.py", "--auth-only"], dry_run=True)
            run_command(["python", "scripts/02a_gee_export_landsat.py", "--years", "2015", "2020", "2023"], dry_run=True)
            """
        ),
        md("## Step 3 - Validate local Landsat inputs"),
        code(
            """
            run_command(["python", "scripts/02_download_or_prepare_satellite_data.py", "--year", YEAR], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 4 - Compute LST\n\nFormula: `lst_kelvin = thermal_band * 0.00341802 + 149.0`; `lst_celsius = lst_kelvin - 273.15`."),
        code(
            """
            run_command(["python", "scripts/03_compute_lst.py", "--year", YEAR], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 5 - Inspect the LST raster metadata"),
        code(
            """
            lst_path = project_path(f"data/processed/lst/lst_ibadan_{YEAR}_celsius.tif")
            if lst_path.exists():
                print(raster_info(lst_path))
                print(raster_stats(lst_path))
            else:
                print("LST raster not found yet.")
            """
        ),
        md("## Step 6 - Plot the LST raster when available"),
        code(
            """
            plot_raster(lst_path, f"Ibadan Land Surface Temperature {YEAR}", cmap="inferno")
            """
        ),
    ],
    "03_urban_indices_exploration.ipynb": [
        md(
            """
            # 03 Urban Indices Exploration

            This notebook computes and inspects NDVI, NDBI, MNDWI, and BSI. These layers explain vegetation,
            built-up intensity, moisture/water signal, and bare-soil exposure.
            """
        ),
        code(SETUP.replace("NOTEBOOK_TITLE", "Urban Indices Exploration")),
        md("## Step 1 - Check reflectance band availability"),
        code(
            """
            import pandas as pd

            band_patterns = {
                "blue / SR_B2": [f"*{YEAR}*SR_B2*.tif", f"*{YEAR}*SR_B2*.TIF"],
                "green / SR_B3": [f"*{YEAR}*SR_B3*.tif", f"*{YEAR}*SR_B3*.TIF"],
                "red / SR_B4": [f"*{YEAR}*SR_B4*.tif", f"*{YEAR}*SR_B4*.TIF"],
                "nir / SR_B5": [f"*{YEAR}*SR_B5*.tif", f"*{YEAR}*SR_B5*.TIF"],
                "swir1 / SR_B6": [f"*{YEAR}*SR_B6*.tif", f"*{YEAR}*SR_B6*.TIF"],
            }
            rows = []
            for band, patterns in band_patterns.items():
                matches = find_files("data/raw/landsat", patterns)
                rows.append({"band": band, "count": len(matches), "first_match": str(matches[0].relative_to(PROJECT_ROOT)) if matches else ""})
            pd.DataFrame(rows)
            """
        ),
        md(
            """
            ## Step 2 - Review formulas

            - NDVI = `(NIR - RED) / (NIR + RED)`
            - NDBI = `(SWIR1 - NIR) / (SWIR1 + NIR)`
            - MNDWI = `(GREEN - SWIR1) / (GREEN + SWIR1)`
            - BSI = `((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))`
            """
        ),
        code(
            """
            run_command(["python", "scripts/04_compute_urban_indices.py", "--year", YEAR], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 3 - Inspect generated index rasters"),
        code(
            """
            import pandas as pd

            index_paths = {
                "NDVI": project_path(f"data/processed/indices/ndvi_{YEAR}.tif"),
                "NDBI": project_path(f"data/processed/indices/ndbi_{YEAR}.tif"),
                "MNDWI": project_path(f"data/processed/indices/mndwi_{YEAR}.tif"),
                "BSI": project_path(f"data/processed/indices/bsi_{YEAR}.tif"),
            }
            rows = []
            for name, path in index_paths.items():
                if path.exists():
                    rows.append({"index": name, **raster_stats(path)})
                else:
                    rows.append({"index": name, "min": None, "mean": None, "max": None, "valid_pixels": 0})
            pd.DataFrame(rows)
            """
        ),
        md("## Step 4 - Plot each index"),
        code(
            """
            cmaps = {"NDVI": "RdYlGn", "NDBI": "YlOrBr", "MNDWI": "Blues", "BSI": "copper"}
            for name, path in index_paths.items():
                plot_raster(path, f"{name} {YEAR}", cmap=cmaps[name])
            """
        ),
        md("## Step 5 - Quick interpretation prompts\n\nUse these questions to write your analysis notes after plotting."),
        code(
            """
            prompts = [
                "Where are low-NDVI surfaces concentrated?",
                "Do high-NDBI zones correspond to high LST zones?",
                "Are water/moisture signals visible in MNDWI?",
                "Does BSI separate bare/peri-urban surfaces from dense built-up areas?",
            ]
            for item in prompts:
                print("-", item)
            """
        ),
    ],
    "04_esda_exploration.ipynb": [
        md(
            """
            # 04 ESDA Exploration

            This notebook runs and interprets spatial autocorrelation: Global Moran's I, Local Moran's I/LISA,
            and Getis-Ord Gi* hot spot analysis.
            """
        ),
        code(SETUP.replace("NOTEBOOK_TITLE", "ESDA Exploration")),
        md("## Step 1 - Check prerequisite surfaces"),
        code(
            """
            import pandas as pd

            prereqs = {
                "LST raster": f"data/processed/lst/lst_ibadan_{YEAR}_celsius.tif",
                "NDVI raster": f"data/processed/indices/ndvi_{YEAR}.tif",
                "NDBI raster": f"data/processed/indices/ndbi_{YEAR}.tif",
                "UHI intensity": f"data/processed/uhi/uhi_intensity_{YEAR}.tif",
            }
            pd.DataFrame(path_status(prereqs))
            """
        ),
        md("## Step 2 - Compute UHI intensity if needed"),
        code(
            """
            run_command(["python", "scripts/05_compute_uhi_intensity.py", "--year", YEAR, "--reference", "auto"], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 3 - Run ESDA for LST"),
        code(
            """
            run_command(["python", "scripts/06_run_esda.py", "--target", "lst", "--year", YEAR], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 4 - Read Global Moran's I result"),
        code(
            """
            import pandas as pd

            moran_path = project_path(f"data/processed/esda/morans_i_{YEAR}.csv")
            if moran_path.exists():
                display(pd.read_csv(moran_path))
            else:
                print("Moran's I table not found yet.")
            """
        ),
        md("## Step 5 - Map LISA clusters"),
        code(
            """
            lisa_path = project_path(f"data/processed/esda/lisa_clusters_{YEAR}.gpkg")
            if lisa_path.exists():
                lisa = read_vector(lisa_path)
                display(lisa[["grid_id", "lisa_i", "lisa_p", "lisa_cluster"]].head())
                ax = lisa.plot(column="lisa_cluster", categorical=True, legend=True, figsize=(9, 8), edgecolor="none")
                ax.set_title(f"LISA clusters {YEAR}")
                ax.set_axis_off()
            else:
                print("LISA output not found yet.")
            """
        ),
        md("## Step 6 - Map Getis-Ord Gi* hot spots"),
        code(
            """
            gi_path = project_path(f"data/processed/esda/gistar_hotspots_{YEAR}.gpkg")
            if gi_path.exists():
                gi = read_vector(gi_path)
                display(gi[["grid_id", "gi_z", "gi_p", "gistar_cluster"]].head())
                ax = gi.plot(column="gistar_cluster", categorical=True, legend=True, figsize=(9, 8), edgecolor="none")
                ax.set_title(f"Getis-Ord Gi* hot spots {YEAR}")
                ax.set_axis_off()
            else:
                print("Gi* output not found yet.")
            """
        ),
    ],
    "05_gwr_exploration.ipynb": [
        md(
            """
            # 05 GWR Exploration

            This notebook prepares and interprets the geographically weighted regression model:
            `LST = beta0 + beta1(NDVI) + beta2(NDBI) + beta3(Population Density) + beta4(Built-up Density) + error`.
            """
        ),
        code(SETUP.replace("NOTEBOOK_TITLE", "GWR Exploration")),
        md("## Step 1 - Check model inputs\n\nPopulation and built-up rasters may come from WorldPop/GHSL prep scripts or your own aligned rasters."),
        code(
            """
            import pandas as pd

            model_inputs = {
                "LST": f"data/processed/lst/lst_ibadan_{YEAR}_celsius.tif",
                "NDVI": f"data/processed/indices/ndvi_{YEAR}.tif",
                "NDBI": f"data/processed/indices/ndbi_{YEAR}.tif",
                "population density": f"data/processed/vulnerability/population_density_{YEAR}.tif",
                "built-up density": f"data/processed/vulnerability/built_up_density_{YEAR}.tif",
            }
            pd.DataFrame(path_status(model_inputs))
            """
        ),
        md("## Step 2 - Preview supporting data prep commands"),
        code(
            """
            run_command(["python", "scripts/02b_prepare_worldpop.py", "--year", YEAR], dry_run=True)
            run_command(["python", "scripts/02c_prepare_ghsl.py", "--year", YEAR], dry_run=True)
            """
        ),
        md("## Step 3 - Run GWR"),
        code(
            """
            run_command([
                "python", "scripts/07_run_gwr.py",
                "--year", YEAR,
                "--dependent", "lst",
                "--predictors", "ndvi", "ndbi", "population_density", "built_up_density",
            ], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 4 - Inspect the model grid and results"),
        code(
            """
            gwr_path = project_path(f"data/processed/gwr/gwr_results_{YEAR}.gpkg")
            if gwr_path.exists():
                gwr = read_vector(gwr_path)
                display(gwr.head())
                print(gwr.columns.tolist())
            else:
                print("GWR results not found yet.")
            """
        ),
        md("## Step 5 - Read model summary"),
        code(
            """
            summary_path = project_path(f"data/processed/gwr/gwr_summary_{YEAR}.txt")
            if summary_path.exists():
                print(summary_path.read_text(encoding="utf-8")[:4000])
            else:
                print("GWR summary not found yet.")
            """
        ),
        md("## Step 6 - Map local coefficients and local R2"),
        code(
            """
            if gwr_path.exists():
                for column in ["coef_ndvi", "coef_ndbi", "coef_population_density", "coef_built_up_density", "local_r2", "gwr_residual"]:
                    if column in gwr.columns:
                        ax = gwr.plot(column=column, legend=True, figsize=(8, 7), cmap="coolwarm", edgecolor="none")
                        ax.set_title(column)
                        ax.set_axis_off()
            """
        ),
    ],
    "06_vulnerability_exploration.ipynb": [
        md(
            """
            # 06 Heat Vulnerability Exploration

            This notebook builds and interprets the Heat Vulnerability Index from exposure, sensitivity,
            and low adaptive capacity indicators using `config/ahp_weights.yml`.
            """
        ),
        code(SETUP.replace("NOTEBOOK_TITLE", "Vulnerability Exploration")),
        md("## Step 1 - Load HVI weights"),
        code(
            """
            weights = load_yaml_config("config/ahp_weights.yml")
            weights
            """
        ),
        md("## Step 2 - Check HVI input layers"),
        code(
            """
            import pandas as pd

            hvi_inputs = {
                "LST mean / exposure": f"data/processed/lst/lst_ibadan_{YEAR}_celsius.tif",
                "UHI intensity / exposure": f"data/processed/uhi/uhi_intensity_{YEAR}.tif",
                "hotspot membership / exposure": f"data/processed/vulnerability/hotspot_membership_{YEAR}.tif",
                "population density / sensitivity": f"data/processed/vulnerability/population_density_{YEAR}.tif",
                "built-up density / sensitivity": f"data/processed/vulnerability/built_up_density_{YEAR}.tif",
                "NDVI / adaptive capacity": f"data/processed/indices/ndvi_{YEAR}.tif",
                "distance to green space / adaptive capacity": f"data/processed/vulnerability/distance_to_green_space_{YEAR}.tif",
                "distance to water / adaptive capacity": f"data/processed/vulnerability/distance_to_water_{YEAR}.tif",
            }
            pd.DataFrame(path_status(hvi_inputs))
            """
        ),
        md("## Step 3 - Preview optional supporting prep commands"),
        code(
            """
            run_command(["python", "scripts/02b_prepare_worldpop.py", "--year", YEAR], dry_run=True)
            run_command(["python", "scripts/02c_prepare_ghsl.py", "--year", YEAR], dry_run=True)
            run_command(["python", "scripts/02d_prepare_osm_layers.py", "--year", YEAR], dry_run=True)
            """
        ),
        md("## Step 4 - Build HVI rasters"),
        code(
            """
            run_command(["python", "scripts/08_build_vulnerability_index.py", "--weights", "config/ahp_weights.yml", "--year", YEAR], dry_run=not RUN_COMMANDS)
            """
        ),
        md("## Step 5 - Inspect generated HVI outputs"),
        code(
            """
            hvi_outputs = {
                "Heat Exposure Index": project_path(f"data/processed/vulnerability/heat_exposure_index_{YEAR}.tif"),
                "Sensitivity Index": project_path(f"data/processed/vulnerability/sensitivity_index_{YEAR}.tif"),
                "Adaptive Capacity Index": project_path(f"data/processed/vulnerability/adaptive_capacity_index_{YEAR}.tif"),
                "Heat Vulnerability Index": project_path(f"data/processed/vulnerability/heat_vulnerability_index_{YEAR}.tif"),
            }
            for name, path in hvi_outputs.items():
                print("\\n", name)
                if path.exists():
                    print(raster_info(path))
                    print(raster_stats(path))
                    plot_raster(path, f"{name} {YEAR}", cmap="magma_r" if "Vulnerability" in name else "viridis")
                else:
                    print("Not generated yet:", path.relative_to(PROJECT_ROOT))
            """
        ),
        md("## Step 6 - Review LGA ranking"),
        code(
            """
            import pandas as pd

            ranking_path = project_path(f"data/processed/tables/ibadan_hvi_ranking_{YEAR}.csv")
            if ranking_path.exists():
                ranking = pd.read_csv(ranking_path)
                display(ranking)
                ranking.plot.barh(x="lga_name", y="hvi_mean", figsize=(8, 6), legend=False, title=f"Ibadan HVI ranking {YEAR}")
            else:
                print("HVI ranking table not found yet.")
            """
        ),
        md("## Step 7 - Generate final outputs and report"),
        code(
            """
            run_command(["python", "scripts/09_generate_outputs.py", "--year", YEAR], dry_run=not RUN_COMMANDS)
            """
        ),
    ],
}


def main() -> None:
    for name, cells in NOTEBOOKS.items():
        path = NOTEBOOK_DIR / name
        path.write_text(json.dumps(nb(cells), indent=2), encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
