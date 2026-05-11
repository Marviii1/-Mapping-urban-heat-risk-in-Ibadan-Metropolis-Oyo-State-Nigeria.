# Environment Notes

This project is designed to run inside an existing Python GIS environment named `gis_env`.

Do not create a new conda or mamba environment for the default workflow.

Activate the environment:

```bash
mamba activate gis_env
```

or

```bash
conda activate gis_env
```

Check dependencies:

```bash
python scripts/00_check_dependencies.py
```

If dependencies are missing, install them into `gis_env` only after reviewing the checker output. A typical command is:

```bash
mamba install -c conda-forge geopandas rasterio rioxarray numpy pandas matplotlib shapely pyproj fiona rasterstats libpysal esda splot scikit-learn statsmodels scipy pyyaml tqdm streamlit folium leafmap geemap osmnx
pip install mgwr pymannkendall
```
