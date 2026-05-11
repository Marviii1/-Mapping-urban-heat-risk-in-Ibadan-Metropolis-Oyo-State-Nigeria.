# Ibadan Urban Heat Risk Summary Report (2015)

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
| Land Surface Temperature | 23.447 | 28.475 | 50.162 | 2.934 |
| Urban Heat Island Intensity | -3.547 | 1.481 | 23.169 | 2.934 |
| Normalized Difference Vegetation Index | 0.058 | 0.400 | 0.704 | 0.105 |
| Normalized Difference Built-up Index | -0.359 | -0.123 | 0.745 | 0.101 |
| Heat Vulnerability Index | 0.061 | 0.240 | 0.732 | 0.105 |
| Heat Exposure Index | 0.000 | 0.188 | 1.000 | 0.110 |
| Sensitivity Index | 0.000 | 0.047 | 0.920 | 0.111 |
| Adaptive Capacity Index | 0.022 | 0.407 | 0.869 | 0.140 |

## Generated Maps

| Map | File |
|---|---|
| Lst | `outputs/maps/lst_2015.png` |
| Uhi | `outputs/maps/uhi_2015.png` |
| Ndvi | `outputs/maps/ndvi_2015.png` |
| Ndbi | `outputs/maps/ndbi_2015.png` |
| Hvi | `outputs/maps/hvi_2015.png` |
| Heat Exposure | `outputs/maps/heat_exposure_2015.png` |
| Sensitivity | `outputs/maps/sensitivity_2015.png` |
| Adaptive Capacity | `outputs/maps/adaptive_capacity_2015.png` |
| Uhi Classes | `outputs/maps/uhi_classes_2015.png` |
| Lisa Clusters | `outputs/maps/lisa_clusters_2015.png` |
| Gistar Hotspots | `outputs/maps/gistar_hotspots_2015.png` |
| Gwr Local R2 | `outputs/maps/gwr_local_r2_2015.png` |
| Gwr Coef Ndvi | `outputs/maps/gwr_coef_ndvi_2015.png` |
| Gwr Coef Ndbi | `outputs/maps/gwr_coef_ndbi_2015.png` |
| Gwr Coef Built Up Density | `outputs/maps/gwr_coef_built_up_density_2015.png` |

## Generated Tables

| Table | File |
|---|---|
| Lga Lst Summary | `outputs/tables/lga_lst_summary_2015.csv` |
| Lga Hvi Summary | `outputs/tables/lga_hvi_summary_2015.csv` |
| Hvi Ranking | `outputs/tables/ibadan_hvi_ranking_2015.csv` |
| Morans I | `outputs/tables/morans_i_2015.csv` |
| Gwr Correlations | `outputs/tables/gwr_input_correlations_2015.csv` |
| Gwr Vif | `outputs/tables/gwr_input_vif_2015.csv` |
| Gwr Ols Coefficients | `outputs/tables/gwr_global_ols_coefficients_2015.csv` |

## Interpretation Notes

- High LST and positive UHI indicate areas of strong heat exposure.
- High-High LISA and Gi* hot spots are statistically meaningful heat clusters.
- Negative NDVI coefficients in GWR support vegetation cooling effects.
- Positive NDBI and built-up density coefficients support urban surface warming effects.
- High HVI zones should be prioritised for greening, shade, cool roofs, and heat-health planning.