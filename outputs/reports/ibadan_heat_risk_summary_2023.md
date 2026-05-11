# Ibadan Urban Heat Risk Summary Report (2023)

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
| Land Surface Temperature | 28.065 | 34.932 | 47.793 | 3.362 |
| Urban Heat Island Intensity | -4.845 | 2.022 | 14.884 | 3.362 |
| Normalized Difference Vegetation Index | -0.194 | 0.427 | 0.814 | 0.131 |
| Normalized Difference Built-up Index | -0.414 | -0.063 | 0.365 | 0.114 |
| Heat Vulnerability Index | 0.047 | 0.294 | 0.771 | 0.120 |
| Heat Exposure Index | 0.000 | 0.348 | 1.000 | 0.170 |
| Sensitivity Index | 0.000 | 0.048 | 0.881 | 0.104 |
| Adaptive Capacity Index | 0.131 | 0.450 | 0.890 | 0.128 |

## Generated Maps

| Map | File |
|---|---|
| Lst | `outputs/maps/lst_2023.png` |
| Uhi | `outputs/maps/uhi_2023.png` |
| Ndvi | `outputs/maps/ndvi_2023.png` |
| Ndbi | `outputs/maps/ndbi_2023.png` |
| Hvi | `outputs/maps/hvi_2023.png` |
| Heat Exposure | `outputs/maps/heat_exposure_2023.png` |
| Sensitivity | `outputs/maps/sensitivity_2023.png` |
| Adaptive Capacity | `outputs/maps/adaptive_capacity_2023.png` |
| Uhi Classes | `outputs/maps/uhi_classes_2023.png` |
| Lisa Clusters | `outputs/maps/lisa_clusters_2023.png` |
| Gistar Hotspots | `outputs/maps/gistar_hotspots_2023.png` |
| Gwr Local R2 | `outputs/maps/gwr_local_r2_2023.png` |
| Gwr Coef Ndvi | `outputs/maps/gwr_coef_ndvi_2023.png` |
| Gwr Coef Ndbi | `outputs/maps/gwr_coef_ndbi_2023.png` |
| Gwr Coef Built Up Density | `outputs/maps/gwr_coef_built_up_density_2023.png` |

## Generated Tables

| Table | File |
|---|---|
| Lga Lst Summary | `outputs/tables/lga_lst_summary_2023.csv` |
| Lga Hvi Summary | `outputs/tables/lga_hvi_summary_2023.csv` |
| Hvi Ranking | `outputs/tables/ibadan_hvi_ranking_2023.csv` |
| Morans I | `outputs/tables/morans_i_2023.csv` |
| Gwr Correlations | `outputs/tables/gwr_input_correlations_2023.csv` |
| Gwr Vif | `outputs/tables/gwr_input_vif_2023.csv` |
| Gwr Ols Coefficients | `outputs/tables/gwr_global_ols_coefficients_2023.csv` |

## Interpretation Notes

- High LST and positive UHI indicate areas of strong heat exposure.
- High-High LISA and Gi* hot spots are statistically meaningful heat clusters.
- Negative NDVI coefficients in GWR support vegetation cooling effects.
- Positive NDBI and built-up density coefficients support urban surface warming effects.
- High HVI zones should be prioritised for greening, shade, cool roofs, and heat-health planning.