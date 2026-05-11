from __future__ import annotations

import importlib.util


REQUIRED_IMPORTS = {
    "geopandas": "geopandas",
    "rasterio": "rasterio",
    "rioxarray": "rioxarray",
    "xarray": "xarray",
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "shapely": "shapely",
    "pyproj": "pyproj",
    "fiona": "fiona",
    "rasterstats": "rasterstats",
    "libpysal": "libpysal",
    "esda": "esda",
    "splot": "splot",
    "sklearn": "scikit-learn",
    "statsmodels": "statsmodels",
    "scipy": "scipy",
    "yaml": "pyyaml",
    "tqdm": "tqdm",
    "requests": "requests",
    "streamlit": "streamlit",
    "folium": "folium",
    "leafmap": "leafmap",
    "geemap": "geemap",
    "ee": "earthengine-api",
    "osmnx": "osmnx",
    "mgwr": "mgwr",
    "pymannkendall": "pymannkendall",
}


CONDA_FORGE_PACKAGES = [
    "geopandas",
    "rasterio",
    "rioxarray",
    "numpy",
    "pandas",
    "matplotlib",
    "shapely",
    "pyproj",
    "fiona",
    "rasterstats",
    "libpysal",
    "esda",
    "splot",
    "scikit-learn",
    "statsmodels",
    "scipy",
    "pyyaml",
    "tqdm",
    "requests",
    "streamlit",
    "folium",
    "leafmap",
    "geemap",
    "osmnx",
]

PIP_PACKAGES = ["mgwr", "pymannkendall", "earthengine-api"]


def is_importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def main() -> int:
    missing = [
        package_name
        for module_name, package_name in REQUIRED_IMPORTS.items()
        if not is_importable(module_name)
    ]

    if not missing:
        print("All required dependencies are available in gis_env.")
        return 0

    print("Missing dependencies detected in gis_env:")
    for package in missing:
        print(f"  - {package}")

    print("\nActivate your existing environment first:")
    print("  mamba activate gis_env")
    print("  # or")
    print("  conda activate gis_env")

    print("\nSuggested conda-forge install command:")
    print("  mamba install -c conda-forge " + " ".join(CONDA_FORGE_PACKAGES))
    print("\nSuggested pip install command for packages commonly installed from PyPI:")
    print("  pip install " + " ".join(PIP_PACKAGES))
    print("\nNo packages were installed automatically.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
