# Streamlit Cloud Deployment Notes

This project is designed to run the heavy geospatial processing locally in `gis_env`, then publish lightweight outputs to Streamlit Cloud.

## Recommended Deployment Pattern

1. Run the full analysis locally.
2. Generate final web/report artifacts:

```bash
python scripts/09_generate_outputs.py --year 2015
python scripts/09_generate_outputs.py --year 2023
python scripts/09_generate_outputs.py --year 2025
```

3. Commit lightweight artifacts only:

- `outputs/maps/*.png`
- `outputs/tables/*.csv`
- `outputs/reports/*.md`
- `outputs/reports/*.pdf`
- `outputs/catalog/*.csv`
- `outputs/catalog/*.json`

4. Keep large raw and processed rasters out of GitHub unless they are intentionally stored with Git LFS or an external data store.

## Streamlit Cloud Settings

- Main file path: `app/streamlit_app.py`
- Python dependencies: `requirements.txt`
- Linux geospatial packages: `packages.txt`
- Optional app theme: `.streamlit/config.toml`

## Why Precomputed Outputs Are Preferred

Streamlit Cloud is good for presenting results, but it is not ideal for running full Landsat, ESDA, GWR, or HVI processing on every app launch. The dashboard therefore references generated PNG maps, CSV tables, GeoPackage availability, PDF reports, and catalog files. This makes the web version faster, more stable, and easier to reproduce.

## Local Dashboard Test

Run this before pushing to GitHub:

```bash
streamlit run app/streamlit_app.py
```

Then open the app and confirm:

- The selected year has a file status table.
- The output catalog page lists maps, tables, reports, and source files.
- The PDF report download button appears after `09_generate_outputs.py` has run.
- Generated map images render correctly with legends, boundary overlays, north arrows, and scale bars.
