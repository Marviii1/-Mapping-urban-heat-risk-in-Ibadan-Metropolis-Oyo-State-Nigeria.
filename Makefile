# ── Environment ──────────────────────────────────────────────────────────────
check:
	python scripts/00_check_dependencies.py

# ── Study area ───────────────────────────────────────────────────────────────
# Option A: import a pre-built boundary GeoPackage (recommended if you already
#           have the 11 Ibadan LGA polygons as a .gpkg from QGIS/ArcGIS)
import-boundary:
	python scripts/01b_import_prebuilt_boundary.py \
		--gpkg data/raw/boundary/ibadan_lgas.gpkg \
		--layer new_lga_nigeria_2003

# Option B: prepare from a full Nigeria LGA shapefile
prepare:
	python scripts/01_prepare_study_area.py --boundary data/raw/boundary/nigeria_lgas.shp

# Show all LGA names in your shapefile before running prepare:
list-lgas:
	python scripts/01_prepare_study_area.py \
		--boundary data/raw/boundary/nigeria_lgas.shp --list-lgas

# ── Satellite / auxiliary data prep ──────────────────────────────────────────
# Step 1: authenticate GEE (browser opens once)
gee-auth:
	python scripts/02a_gee_export_landsat.py --auth-only

# Step 2: submit export tasks to Google Drive (check tasks at code.earthengine.google.com/tasks)
gee-export:
	python scripts/02a_gee_export_landsat.py --years 2015 2020 2023

# Step 3: after downloading GeoTIFFs from Drive into data/raw/landsat/, clip them to the study boundary
clip-landsat:
	python scripts/02e_clip_landsat_to_boundary.py --years 2015 2020 2023

# Step 4: prepare ancillary data
worldpop:
	python scripts/02b_prepare_worldpop.py --year 2023

worldpop-all:
	python scripts/02b_prepare_worldpop.py --year 2015
	python scripts/02b_prepare_worldpop.py --year 2020
	python scripts/02b_prepare_worldpop.py --year 2023

ghsl:
	python scripts/02c_prepare_ghsl.py --year 2023

ghsl-gee:
	python scripts/02f_gee_export_ghsl.py --year 2023

osm:
	python scripts/02d_prepare_osm_layers.py --year 2023

osm-all:
	python scripts/02d_prepare_osm_layers.py --year 2015
	python scripts/02d_prepare_osm_layers.py --year 2020
	python scripts/02d_prepare_osm_layers.py --year 2023

# Convenience: run all ancillary data prep for a single year
data: worldpop ghsl osm

# Convenience: validate and clip downloaded Landsat before analysis
landsat-ready:
	python scripts/02_download_or_prepare_satellite_data.py --year 2023 --landsat-dir data/raw/landsat
	python scripts/02e_clip_landsat_to_boundary.py --years 2015 2020 2023

# ── Analysis pipeline ─────────────────────────────────────────────────────────
lst:
	python scripts/03_compute_lst.py --year 2023 --landsat-dir data/raw/landsat_clipped

indices:
	python scripts/04_compute_urban_indices.py --year 2023 --landsat-dir data/raw/landsat_clipped

uhi:
	python scripts/05_compute_uhi_intensity.py --year 2023 --reference auto

esda:
	python scripts/06_run_esda.py --target lst --year 2023

gwr:
	python scripts/07_run_gwr.py --year 2023 --dependent lst --predictors ndvi ndbi population_density built_up_density

hvi:
	python scripts/08_build_vulnerability_index.py --weights config/ahp_weights.yml --year 2023

temporal:
	python scripts/10_temporal_comparison.py --years 2015 2020 2023

temporal-lst:
	python scripts/10_temporal_comparison.py --years 2015 2020 2023 --variable lst

temporal-ndvi:
	python scripts/10_temporal_comparison.py --years 2015 2020 2023 --variable ndvi

outputs:
	python scripts/09_generate_outputs.py --year 2023

# ── Dashboard ─────────────────────────────────────────────────────────────────
app:
	streamlit run app/streamlit_app.py

# ── Full pipeline (assumes Landsat files already in data/raw/landsat/) ────────
all: check prepare landsat-ready data lst indices uhi esda gwr hvi outputs
