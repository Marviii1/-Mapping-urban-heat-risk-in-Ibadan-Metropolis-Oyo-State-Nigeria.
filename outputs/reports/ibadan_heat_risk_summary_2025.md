# Ibadan Urban Heat Risk Summary Report (2025)

## Methodology Conceptualisation

- Landsat-derived LST provides the thermal exposure surface.
- NDVI, NDBI, and GHSL built-up density represent urban biophysical heat drivers.
- UHI intensity measures the thermal departure from rural reference pixels.
- ESDA identifies global spatial autocorrelation, LISA clusters, and Gi* hot/cold spots.
- GWR models spatially varying relationships between LST and heat drivers.
- HVI combines exposure, sensitivity, and low adaptive capacity using AHP-style weights.

## Key Raster Statistics

| Layer | Min | Mean | Max | Std |
|---|---:|---:|---:|---:|
| Land Surface Temperature | 27.819 | 34.829 | 48.602 | 3.453 |
| Urban Heat Island Intensity | -5.277 | 1.733 | 15.506 | 3.453 |
| Normalized Difference Vegetation Index | -0.239 | 0.484 | 0.830 | 0.150 |
| Normalized Difference Built-up Index | -0.515 | -0.084 | 0.292 | 0.124 |
| Heat Vulnerability Index | 0.054 | 0.282 | 0.782 | 0.122 |
| Heat Exposure Index | 0.000 | 0.337 | 1.000 | 0.166 |
| Sensitivity Index | 0.000 | 0.048 | 0.881 | 0.104 |
| Adaptive Capacity Index | 0.090 | 0.480 | 0.885 | 0.131 |

## Generated Maps

| Map | File |
|---|---|
| Lst | `outputs/maps/lst_2025.png` |
| Uhi | `outputs/maps/uhi_2025.png` |
| Ndvi | `outputs/maps/ndvi_2025.png` |
| Ndbi | `outputs/maps/ndbi_2025.png` |
| Hvi | `outputs/maps/hvi_2025.png` |
| Heat Exposure | `outputs/maps/heat_exposure_2025.png` |
| Sensitivity | `outputs/maps/sensitivity_2025.png` |
| Adaptive Capacity | `outputs/maps/adaptive_capacity_2025.png` |
| Uhi Classes | `outputs/maps/uhi_classes_2025.png` |
| Lisa Clusters | `outputs/maps/lisa_clusters_2025.png` |
| Gistar Hotspots | `outputs/maps/gistar_hotspots_2025.png` |
| Gwr Local R2 | `outputs/maps/gwr_local_r2_2025.png` |
| Gwr Coef Ndvi | `outputs/maps/gwr_coef_ndvi_2025.png` |
| Gwr Coef Ndbi | `outputs/maps/gwr_coef_ndbi_2025.png` |
| Gwr Coef Built Up Density | `outputs/maps/gwr_coef_built_up_density_2025.png` |

## Generated Tables

| Table | File |
|---|---|
| Lga Lst Summary | `outputs/tables/lga_lst_summary_2025.csv` |
| Lga Hvi Summary | `outputs/tables/lga_hvi_summary_2025.csv` |
| Hvi Ranking | `outputs/tables/ibadan_hvi_ranking_2025.csv` |
| Morans I | `outputs/tables/morans_i_2025.csv` |
| Gwr Correlations | `outputs/tables/gwr_input_correlations_2025.csv` |
| Gwr Vif | `outputs/tables/gwr_input_vif_2025.csv` |
| Gwr Ols Coefficients | `outputs/tables/gwr_global_ols_coefficients_2025.csv` |

## Interpretation Notes

- High LST and positive UHI indicate areas of strong heat exposure.
- High-High LISA and Gi* hot spots are statistically meaningful heat clusters.
- Negative NDVI coefficients in GWR support vegetation cooling effects.
- Positive NDBI and built-up density coefficients support urban surface warming effects.
- High HVI zones should be prioritised for greening, shade, cool roofs, and heat-health planning.