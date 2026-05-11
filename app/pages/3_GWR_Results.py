"""GWR / MGWR Heat Driver Modelling Results."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import (
    PROJECT_ROOT, LGAS_PATH, pp,
    load_raster, load_vector, load_csv,
    render_raster_map, render_vector_map, no_data, sidebar_year,
)

st.set_page_config(page_title="GWR Results", page_icon="📊", layout="wide")
st.title("📊 GWR Heat Driver Modelling")
st.caption(
    "Geographically Weighted Regression — how heat drivers (NDVI, NDBI, "
    "population density, built-up intensity) vary spatially across Ibadan."
)

year = sidebar_year()
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**GWR Predictors**\n"
    "- NDVI · vegetation cooling\n"
    "- NDBI · built-up heating\n"
    "- Population density\n"
    "- Built-up surface fraction\n\n"
    "**Model**\n"
    "Adaptive bandwidth, AIC selection, "
    "standardised predictors."
)

# ── File paths ────────────────────────────────────────────────────────────────
gwr_gpkg    = pp("data/processed/gwr/gwr_results_{y}.gpkg",          y=year)
gwr_summary = pp("data/processed/gwr/gwr_summary_{y}.txt",           y=year)
ndvi_coef   = pp("data/processed/gwr/gwr_ndvi_coefficient_{y}.tif",  y=year)
ndbi_coef   = pp("data/processed/gwr/gwr_ndbi_coefficient_{y}.tif",  y=year)
local_r2    = pp("data/processed/gwr/gwr_local_r2_{y}.tif",          y=year)
residuals   = pp("data/processed/gwr/gwr_residuals_{y}.tif",         y=year)

lgas = load_vector(str(LGAS_PATH))

# ── Check if GWR has been run ─────────────────────────────────────────────────
if not gwr_gpkg.exists() and not ndvi_coef.exists():
    web_maps = [
        pp("outputs/maps/gwr_local_r2_{y}.png", y=year),
        pp("outputs/maps/gwr_coef_ndvi_{y}.png", y=year),
        pp("outputs/maps/gwr_coef_ndbi_{y}.png", y=year),
        pp("outputs/maps/gwr_coef_built_up_density_{y}.png", y=year),
    ]
    web_maps = [path for path in web_maps if path.exists()]
    web_tables = {
        "Global OLS coefficients": pp("outputs/tables/gwr_global_ols_coefficients_{y}.csv", y=year),
        "Input correlations": pp("outputs/tables/gwr_input_correlations_{y}.csv", y=year),
        "VIF diagnostics": pp("outputs/tables/gwr_input_vif_{y}.csv", y=year),
    }
    if web_maps or any(path.exists() for path in web_tables.values()):
        st.markdown("---")
        st.info("Cloud display is using committed GWR PNG/CSV outputs. Local GeoPackage/raster exploration is available in the full desktop project.")
        if web_maps:
            st.subheader("GWR Cartographic Outputs")
            cols = st.columns(2)
            for idx, map_path in enumerate(web_maps):
                with cols[idx % 2]:
                    st.image(str(map_path), caption=str(map_path.relative_to(PROJECT_ROOT)), use_container_width=True)
        st.markdown("---")
        st.subheader("GWR Diagnostic Tables")
        for label, path in web_tables.items():
            df = load_csv(str(path))
            with st.expander(label, expanded=True):
                if df is not None:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{path.name} is not available.")
        st.stop()

    st.markdown("---")
    no_data(
        f"gwr_results_{year}.gpkg",
        f"python scripts/07_run_gwr.py --year {year} "
        f"--dependent lst --predictors ndvi ndbi population_density built_up_density",
    )
    st.markdown(
        "**Prerequisites:** LST, NDVI, NDBI, population density, and built-up "
        "density rasters must all be generated first."
    )
    st.stop()

# ── Summary text ──────────────────────────────────────────────────────────────
if gwr_summary.exists():
    with st.expander("📋 GWR Model Summary", expanded=True):
        st.code(gwr_summary.read_text(encoding="utf-8"), language="text")

st.markdown("---")

# ── Coefficient maps ──────────────────────────────────────────────────────────
st.subheader("Local Coefficient Maps")
st.caption(
    "Each map shows how strongly each predictor influences LST at that location. "
    "Negative NDVI coefficients = vegetation cools. Positive NDBI coefficients = "
    "built-up surfaces heat. Spatial variation reveals where interventions matter most."
)

coef_specs = [
    (ndvi_coef,  "NDVI Coefficient",  "RdYlGn",    "β (NDVI → LST)",   "Negative = cooling effect"),
    (ndbi_coef,  "NDBI Coefficient",  "YlOrRd",    "β (NDBI → LST)",   "Positive = heating effect"),
    (local_r2,   "Local R²",          "viridis",   "R² (0–1)",         "Goodness of fit per location"),
    (residuals,  "GWR Residuals",     "RdBu_r",    "Residual (°C)",    "Spatial pattern of model error"),
]

available_coefs = [(path, *rest) for path, *rest in coef_specs if path.exists()]

if not available_coefs:
    st.warning("Coefficient raster files not found. Check that the GWR script completed successfully.")
else:
    n_cols = min(len(available_coefs), 2)
    rows = [available_coefs[i:i+n_cols] for i in range(0, len(available_coefs), n_cols)]

    for row_specs in rows:
        cols = st.columns(n_cols, gap="medium")
        for col, (path, title, cmap, label, caption) in zip(cols, row_specs):
            with col:
                arr, profile, _ = load_raster(str(path))
                if arr is None:
                    st.warning(f"{title}: file not readable.")
                    continue
                # Symmetric colorscale for coefficients
                valid = arr[np.isfinite(arr)]
                if "Residual" in title or "Coefficient" in title:
                    vabs = float(np.percentile(np.abs(valid), 98)) if valid.size else 1
                    vmin, vmax = -vabs, vabs
                else:
                    vmin, vmax = None, None
                fig = render_raster_map(
                    arr, profile, title=f"{title} — {year}",
                    cmap=cmap, label=label,
                    vmin=vmin, vmax=vmax,
                    lgas=lgas, figsize=(6, 5),
                )
                st.pyplot(fig, use_container_width=True)
                st.caption(caption)
                import matplotlib.pyplot as plt; plt.close(fig)

# ── Coefficient statistics ────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Coefficient Distribution Summary")

coef_stats = []
for path, title, _, label, _ in coef_specs:
    if not path.exists():
        continue
    arr, _, _ = load_raster(str(path))
    if arr is None:
        continue
    valid = arr[np.isfinite(arr)]
    if not valid.size:
        continue
    coef_stats.append({
        "Layer": title,
        "Min": round(float(valid.min()), 4),
        "Q25": round(float(np.percentile(valid, 25)), 4),
        "Median": round(float(np.median(valid)), 4),
        "Q75": round(float(np.percentile(valid, 75)), 4),
        "Max": round(float(valid.max()), 4),
        "Std Dev": round(float(valid.std()), 4),
        "% Positive": round(float((valid > 0).mean() * 100), 1),
    })

if coef_stats:
    col_tbl, col_box = st.columns([2, 3], gap="large")
    with col_tbl:
        st.dataframe(pd.DataFrame(coef_stats), use_container_width=True, hide_index=True)

    with col_box:
        # Box plots of coefficient distributions
        box_data = []
        for path, title, _, _, _ in coef_specs:
            if not path.exists():
                continue
            arr, _, _ = load_raster(str(path))
            if arr is None:
                continue
            valid = arr[np.isfinite(arr)]
            sample = valid[::max(1, len(valid)//2000)]
            for v in sample:
                box_data.append({"Layer": title, "Value": float(v)})

        if box_data:
            box_df = pd.DataFrame(box_data)
            fig_box = px.box(
                box_df, x="Layer", y="Value",
                color="Layer",
                title=f"GWR Coefficient Distributions — {year}",
                template="plotly_dark",
                points=False,
            )
            fig_box.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
            fig_box.update_layout(showlegend=False, xaxis_tickangle=-20,
                                  margin=dict(t=50, b=60))
            st.plotly_chart(fig_box, use_container_width=True)

# ── GWR vector results table ──────────────────────────────────────────────────
if gwr_gpkg.exists():
    st.markdown("---")
    st.subheader("GWR Point Results (Sample)")
    gwr_gdf = load_vector(str(gwr_gpkg))
    if gwr_gdf is not None:
        display_cols = [c for c in gwr_gdf.columns if c != "geometry"]
        n_show = min(200, len(gwr_gdf))
        st.caption(f"Showing first {n_show} of {len(gwr_gdf)} regression points.")
        st.dataframe(
            gwr_gdf[display_cols].head(n_show).round(4),
            use_container_width=True, hide_index=True,
        )

        # Scatter: local R² vs NDVI coefficient
        r2_col   = next((c for c in display_cols if "r2" in c.lower() or "localr2" in c.lower()), None)
        ndvi_col = next((c for c in display_cols if "ndvi" in c.lower() and "coef" in c.lower()), None)
        ndbi_col = next((c for c in display_cols if "ndbi" in c.lower() and "coef" in c.lower()), None)

        if r2_col and ndvi_col:
            st.markdown("---")
            st.subheader("Local R² vs Predictor Coefficients")
            sc_cols = st.columns(2)
            with sc_cols[0]:
                fig_sc = px.scatter(
                    gwr_gdf.sample(min(500, len(gwr_gdf))),
                    x=ndvi_col, y=r2_col,
                    opacity=0.5,
                    title=f"NDVI Coefficient vs Local R² ({year})",
                    labels={ndvi_col: "β NDVI", r2_col: "Local R²"},
                    template="plotly_dark",
                    color_discrete_sequence=["#4A90D9"],
                    trendline="ols",
                )
                st.plotly_chart(fig_sc, use_container_width=True)
            if ndbi_col:
                with sc_cols[1]:
                    fig_sc2 = px.scatter(
                        gwr_gdf.sample(min(500, len(gwr_gdf))),
                        x=ndbi_col, y=r2_col,
                        opacity=0.5,
                        title=f"NDBI Coefficient vs Local R² ({year})",
                        labels={ndbi_col: "β NDBI", r2_col: "Local R²"},
                        template="plotly_dark",
                        color_discrete_sequence=["#E05252"],
                        trendline="ols",
                    )
                    st.plotly_chart(fig_sc2, use_container_width=True)
