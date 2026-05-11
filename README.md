# Ibadan Urban Heat Risk Intelligence System

**Full title:** Urban Heat Island Intensity Mapping, Spatial Autocorrelation Analysis, GWR-Based Heat Driver Modelling, and Thermal Vulnerability Assessment for Ibadan Metropolis, Oyo State, Nigeria.

## Problem Statement

Ibadan is one of Nigeria's largest and fastest-changing urban regions. Dense built-up surfaces, reduced vegetation, transport corridors, and peri-urban expansion can intensify land surface temperatures and expose communities to higher heat stress. This project provides a reproducible geospatial workflow for identifying where heat risk is concentrated, what explains it, and which areas should be prioritized for cooling interventions.

## Why Ibadan?

Ibadan combines dense historic urban LGAs with rapidly transforming peri-urban LGAs. This makes it a strong case study for mapping an urban-rural thermal gradient, comparing core and fringe heat patterns, and supporting planning decisions across metropolitan Oyo State.

## Objectives

- Prepare the Ibadan metropolitan study boundary from Nigeria LGA boundaries.
- Generate dry-season Landsat-derived Land Surface Temperature maps.
- Compute NDVI, NDBI, MNDWI, BSI, and built-up indicators.
- Map Urban Heat Island intensity using rural reference pixels.
- Run Moran's I, LISA, and Getis-Ord Gi* hot spot analysis.
- Model spatially varying heat drivers using GWR or MGWR.
- Build exposure, sensitivity, adaptive capacity, and Heat Vulnerability Index layers.
- Export GIS-ready outputs for ArcGIS, QGIS, and web dashboards.

## Methodology Overview

1. Select Ibadan target LGAs and dissolve them into a metropolitan boundary.
2. Prepare Landsat 8/9 Collection 2 Level-2 imagery for dry-season months.
3. Convert the `ST_B10` thermal band to Celsius using the official scale factor and offset.
4. Compute urban biophysical indices from optical bands.
5. Estimate UHI intensity as pixel LST minus mean rural reference LST.
6. Aggregate raster values to a regular grid for spatial autocorrelation analysis.
7. Fit GWR to explain LST using NDVI, NDBI, population density, and built-up density.
8. Combine weighted indicators into a Heat Vulnerability Index.

## Dataset Requirements

- Nigeria LGA boundary shapefile with Ibadan and Oyo State attributes.
- Landsat 8/9 Collection 2 Level-2 scenes covering Ibadan.
- Optional Sentinel-2, GHSL, WorldPop, ESA WorldCover, and OSM layers.
- Locally prepared population density, built-up density, green-space distance, and water-distance rasters for full HVI modelling.

## Folder Structure

The repository separates raw data, interim products, processed analysis layers, outputs, scripts, reusable source code, docs, and dashboard files. Raw and generated geospatial data are ignored by Git by default.

## Setup

Do not create a new environment for this project. Use your existing Python GIS environment.

**Step 1: Activate existing environment**

```bash
mamba activate gis_env
```

or

```bash
conda activate gis_env
```

**Step 2: Check dependencies**

```bash
python scripts/00_check_dependencies.py
```

If packages are missing, the checker prints clear install suggestions. It does not install anything automatically.

**Step 3: Prepare study area**

```bash
python scripts/01_prepare_study_area.py --boundary data/raw/boundary/nigeria_lgas.shp
```

**Step 4: Clip downloaded Landsat rasters to the Ibadan boundary**

After downloading the Earth Engine GeoTIFFs into `data/raw/landsat/`, run:

```bash
python scripts/02e_clip_landsat_to_boundary.py --years 2015 2023 2025
```

This keeps the raw downloads unchanged and writes boundary-clipped rasters to:

```text
data/raw/landsat_clipped/
```

Use `data/raw/landsat_clipped/` for LST and index processing.

## CLI Execution Guide

```bash
python scripts/00_check_dependencies.py
python scripts/01_prepare_study_area.py --boundary data/raw/boundary/nigeria_lgas.shp
python scripts/02_download_or_prepare_satellite_data.py --year 2023
python scripts/02e_clip_landsat_to_boundary.py --years 2015 2023 2025
python scripts/03_compute_lst.py --year 2023 --landsat-dir data/raw/landsat_clipped
python scripts/04_compute_urban_indices.py --year 2023 --landsat-dir data/raw/landsat_clipped
python scripts/05_compute_uhi_intensity.py --year 2023 --reference auto
python scripts/06_run_esda.py --target lst --year 2023 --resolution 500
python scripts/07_run_gwr.py --year 2023 --dependent lst --predictors ndvi ndbi built_up_density --resolution 500 --bandwidth 500
python scripts/08_build_vulnerability_index.py --weights config/ahp_weights.yml --year 2023
python scripts/09_generate_outputs.py --year 2023
```

For the current multi-year workflow, repeat the analysis for:

```bash
python scripts/09_generate_outputs.py --year 2015
python scripts/09_generate_outputs.py --year 2023
python scripts/09_generate_outputs.py --year 2025
```

Makefile shortcuts are also available:

```bash
make check
make prepare
make landsat-ready
make lst
make indices
make uhi
make esda
make gwr
make hvi
make outputs
```

## Expected Outputs

- `data/processed/uhi/ibadan_lgas.gpkg`
- `data/processed/uhi/ibadan_metropolitan_boundary.gpkg`
- `data/processed/tables/ibadan_lga_list.csv`
- `data/processed/lst/lst_ibadan_2023_celsius.tif`
- `data/processed/indices/ndvi_2023.tif`
- `data/processed/indices/ndbi_2023.tif`
- `data/processed/indices/mndwi_2023.tif`
- `data/processed/indices/bsi_2023.tif`
- `data/processed/uhi/uhi_intensity_2023.tif`
- `data/processed/uhi/uhi_classes_2023.tif`
- `data/processed/esda/morans_i_2023.csv`
- `data/processed/esda/lisa_clusters_2023.gpkg`
- `data/processed/esda/gistar_hotspots_2023.gpkg`
- `data/processed/gwr/gwr_results_2023.gpkg`
- `data/processed/gwr/gwr_summary_2023.txt`
- `data/processed/vulnerability/heat_vulnerability_index_2023.tif`
- `outputs/reports/ibadan_heat_risk_summary_2023.md`
- `outputs/reports/ibadan_heat_risk_summary_2023.pdf`
- `outputs/catalog/output_catalog_2023.csv`
- `outputs/maps/lst_2023.png`
- `outputs/maps/uhi_2023.png`
- `outputs/maps/hvi_2023.png`

## Dashboard

Run the Streamlit dashboard with:

```bash
streamlit run app/streamlit_app.py
```

The dashboard includes project overview, study area status, LST exploration, UHI and hot spot outputs, GWR results, Heat Vulnerability Index, LGA ranking, and recommended intervention zones.

The dashboard also includes an **Outputs & Report** page that references the generated map PNGs, CSV tables, Markdown reports, PDF reports, and output catalogs. This page is intended for GitHub and Streamlit Cloud presentation after the local GIS processing has been completed.

## Streamlit Cloud Deployment

This repository is structured so the heavy geospatial analysis can be run locally in `gis_env`, while Streamlit Cloud serves lightweight, precomputed outputs.

- Main app file: `app/streamlit_app.py`
- Python packages: `requirements.txt`
- Linux GIS libraries for Streamlit Cloud: `packages.txt`
- Theme/server settings: `.streamlit/config.toml`
- Deployment notes: `docs/streamlit_cloud_deployment.md`

Recommended web artifacts to commit:

- `outputs/maps/*.png`
- `outputs/tables/*.csv`
- `outputs/reports/*.md`
- `outputs/reports/*.pdf`
- `outputs/catalog/*.csv`
- `outputs/catalog/*.json`

Large raw rasters, processed rasters, and GeoPackages should normally remain local or be managed with Git LFS/external storage.

## Limitations

- Landsat thermal outputs are sensitive to cloud masking, acquisition date, atmospheric conditions, and seasonal selection.
- UHI reference definitions should be reviewed against local land cover and peri-urban context.
- GWR results require careful multicollinearity checks, bandwidth diagnostics, and local interpretation.
- HVI weights are configurable and should be validated with stakeholders or sensitivity analysis.

## Future Improvements

- Add automated Earth Engine export recipes.
- Add cloud/shadow QA masking workflows.
- Add MGWR model comparison.
- Add QGIS/ArcGIS cartographic layouts.
- Add validation against in-situ weather station observations.
- Add scenario modelling for tree canopy, cool roofs, and water-sensitive urban design.

## Author

Prepared as an academic and professional portfolio geospatial intelligence project for Ibadan Metropolis, Oyo State, Nigeria.
#