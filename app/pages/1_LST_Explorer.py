"""Land Surface Temperature Explorer."""
from __future__ import annotations
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import (
    PROJECT_ROOT, LGAS_PATH, YEARS, pp,
    load_raster, load_vector, load_csv,
    render_raster_map, no_data, sidebar_year,
)

st.set_page_config(page_title="LST Explorer", page_icon="🗺️", layout="wide")
st.title("🗺️ Land Surface Temperature Explorer")
st.caption("Landsat 8/9 Collection 2 Level-2 · Band ST_B10 · Dry season composite")

year = sidebar_year()
st.sidebar.markdown("---")
st.sidebar.info(
    "**LST Formula**\n\n"
    "`DN × 0.00341802 + 149.0 → Kelvin`\n\n"
    "`Kelvin − 273.15 → Celsius`"
)

# ── Load data ─────────────────────────────────────────────────────────────────
lst_path = pp("data/processed/lst/lst_ibadan_{y}_celsius.tif", y=year)
arr, profile, bounds = load_raster(str(lst_path))
lgas = load_vector(str(LGAS_PATH))

if arr is None:
    st.markdown("---")
    no_data(
        f"lst_ibadan_{year}_celsius.tif",
        f"python scripts/02a_gee_export_landsat.py --setup\n"
        f"# download TIFFs to data/raw/landsat/, then:\n"
        f"python scripts/03_compute_lst.py --year {year}",
    )
    st.stop()

valid = arr[np.isfinite(arr)]

# ── Summary metrics ───────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Min LST", f"{float(valid.min()):.1f} °C")
c2.metric("Max LST", f"{float(valid.max()):.1f} °C")
c3.metric("Mean LST", f"{float(valid.mean()):.1f} °C")
c4.metric("Std Dev", f"{float(valid.std()):.1f} °C")
st.markdown("---")

# ── Main layout: map + distribution ──────────────────────────────────────────
col_map, col_chart = st.columns([3, 2], gap="large")

with col_map:
    st.subheader(f"LST Map — {year}")
    fig = render_raster_map(
        arr, profile,
        title=f"Land Surface Temperature — Ibadan {year}",
        cmap="inferno",
        label="°C",
        lgas=lgas,
        figsize=(8, 7),
    )
    st.pyplot(fig, use_container_width=True)

    import matplotlib.pyplot as plt
    plt.close(fig)

with col_chart:
    st.subheader("Temperature Distribution")
    # Histogram
    sample = valid[::max(1, len(valid)//5000)]   # downsample for speed
    fig_hist = px.histogram(
        x=sample, nbins=60,
        labels={"x": "LST (°C)", "y": "Pixel count"},
        title=f"LST Frequency Distribution — {year}",
        template="plotly_dark",
        color_discrete_sequence=["#FF6B35"],
    )
    fig_hist.update_layout(bargap=0.05, showlegend=False,
                           margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_hist, use_container_width=True)

    # Percentile table
    pcts = [10, 25, 50, 75, 90, 95, 99]
    perc_vals = [round(float(np.percentile(valid, p)), 2) for p in pcts]
    pct_df = pd.DataFrame({"Percentile (%)": pcts, "LST (°C)": perc_vals})
    st.dataframe(pct_df, use_container_width=True, hide_index=True)

# ── Per-LGA bar chart ─────────────────────────────────────────────────────────
if lgas is not None:
    st.markdown("---")
    st.subheader(f"Mean LST per LGA — {year}")

    try:
        import rasterio
        from rasterio.features import rasterize

        with rasterio.open(str(lst_path)) as src:
            transform = src.transform
            shape = (src.height, src.width)
            crs = src.crs

        lgas_proj = lgas.to_crs(crs)
        records = []
        for _, row in lgas_proj.iterrows():
            mask = rasterize(
                [(row.geometry.__geo_interface__, 1)],
                out_shape=shape, transform=transform, fill=0, dtype="uint8",
            ).astype(bool)
            vals = arr[mask & np.isfinite(arr)]
            if not vals.size:
                continue
            records.append({
                "LGA": str(row.get("LGA", row.get("lga_name", ""))),
                "Zone": str(row.get("zone_type", "")),
                "Mean LST (°C)": round(float(vals.mean()), 2),
                "Max LST (°C)": round(float(vals.max()), 2),
                "Min LST (°C)": round(float(vals.min()), 2),
                "Std Dev": round(float(vals.std()), 2),
            })

        if records:
            lga_df = pd.DataFrame(records).sort_values("Mean LST (°C)", ascending=False)

            col_bar, col_tbl = st.columns([3, 2], gap="large")
            with col_bar:
                colour_map = {"core_urban": "#E05252", "peri_urban": "#4A90D9"}
                colours = [colour_map.get(z, "#888") for z in lga_df["Zone"]]
                fig_bar = go.Figure(go.Bar(
                    x=lga_df["LGA"], y=lga_df["Mean LST (°C)"],
                    marker_color=colours,
                    text=lga_df["Mean LST (°C)"].apply(lambda v: f"{v:.1f}°C"),
                    textposition="outside",
                ))
                fig_bar.update_layout(
                    title=f"Mean LST by LGA ({year})",
                    template="plotly_dark",
                    xaxis_tickangle=-35,
                    yaxis_title="Mean LST (°C)",
                    showlegend=False,
                    margin=dict(l=10, r=10, t=40, b=60),
                )
                # Zone legend via annotation
                fig_bar.add_annotation(
                    x=0.01, y=0.98, xref="paper", yref="paper",
                    text="🟥 Core Urban   🟦 Peri-urban",
                    showarrow=False, font_size=10, align="left",
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_tbl:
                st.dataframe(
                    lga_df[["LGA", "Zone", "Mean LST (°C)", "Max LST (°C)", "Min LST (°C)", "Std Dev"]],
                    use_container_width=True, hide_index=True,
                )

                # Zone type mean comparison
                st.markdown("**Zone-type comparison**")
                zone_agg = lga_df.groupby("Zone")["Mean LST (°C)"].mean().reset_index()
                zone_agg.columns = ["Zone", "Mean LST (°C)"]
                zone_agg["Mean LST (°C)"] = zone_agg["Mean LST (°C)"].round(2)
                if len(zone_agg) == 2:
                    core = zone_agg.loc[zone_agg["Zone"] == "core_urban", "Mean LST (°C)"].values
                    peri = zone_agg.loc[zone_agg["Zone"] == "peri_urban", "Mean LST (°C)"].values
                    if core.size and peri.size:
                        delta = round(float(core[0]) - float(peri[0]), 2)
                        st.metric("Urban-Rural Contrast", f"{delta:+.2f} °C",
                                  help="Core urban mean minus peri-urban mean LST")
                st.dataframe(zone_agg, use_container_width=True, hide_index=True)

    except Exception as exc:
        st.warning(f"Could not compute per-LGA statistics: {exc}")
