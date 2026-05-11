# Methodology

The workflow combines remote sensing, spatial statistics, geographically weighted regression, and multicriteria vulnerability assessment.

1. Boundary preparation selects the Ibadan target LGAs from a Nigeria LGA layer and dissolves them into one metropolitan boundary.
2. Landsat Collection 2 Level-2 thermal data are converted to Celsius using `ST_B10 * 0.00341802 + 149.0 - 273.15`.
3. NDVI, NDBI, MNDWI, and BSI are derived from Landsat optical bands.
4. UHI intensity is calculated as pixel LST minus mean rural reference LST.
5. Spatial autocorrelation is assessed with Global Moran's I, Local Moran's I, and Getis-Ord Gi*.
6. GWR models spatially varying relationships between LST and urban/environmental predictors.
7. HVI combines exposure, sensitivity, and low adaptive capacity using configurable AHP-style weights.

## Auxiliary Data Assumptions

- WorldPop 2020 population data are used as a population-density proxy where year-specific population rasters are unavailable. The Nigeria-wide raster is clipped and reprojected to the Ibadan metropolitan boundary for each analysis year.
- GHSL built-up surface rasters are prepared per available GHSL epoch and clipped to the Ibadan boundary. Where an exact analysis year is unavailable, the nearest GHSL epoch is used as a built-up-density proxy.
- OSM-derived distance-to-green-space and distance-to-water layers are generated from current OpenStreetMap features and used as static adaptive-capacity proxies across the study years. This assumes that mapped green and water access patterns are sufficiently representative for comparative vulnerability modelling, and it should be treated as a methodological limitation.

## Current Analysis Years

The operational pipeline is currently configured around the prepared Landsat and auxiliary rasters for:

- 2015
- 2023
- 2025
