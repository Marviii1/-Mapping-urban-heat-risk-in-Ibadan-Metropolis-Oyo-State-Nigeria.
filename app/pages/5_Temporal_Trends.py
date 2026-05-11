"""Multi-year temporal change and trend analysis."""
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
    render_raster_map, no_data,
    apply_dashboard_style, render_sidebar_brand, render_sidebar_project_about,
)

st.set_page_config(page_title="Temporal Trends", page_icon=":chart_with_upwards_trend:", layout="wide")
apply_dashboard_style()
st.title("Multi-year Temporal Change Analysis")
st.caption("LST and vegetation change maps, Mann-Kendall trend direction, and LGA-level summaries (2015, 2023, 2025)")

render_sidebar_brand()
st.sidebar.markdown("---")
variable = st.sidebar.selectbox(
    "View", ["lst", "ndvi", "ndbi", "uhi"],
    format_func=lambda v: {
        "lst": "Land Surface Temperature (LST)",
        "ndvi": "Vegetation Index (NDVI)",
        "ndbi": "Built-up Index (NDBI)",
        "uhi": "UHI Intensity",
    }[v],
)
render_sidebar_project_about()
YEARS = [2015, 2023, 2025]
lgas = load_vector(str(LGAS_PATH))

# ── File discovery ────────────────────────────────────────────────────────────
VAR_PATHS = {
    "lst":  "data/processed/lst/lst_ibadan_{y}_celsius.tif",
    "ndvi": "data/processed/indices/ndvi_{y}.tif",
    "ndbi": "data/processed/indices/ndbi_{y}.tif",
    "uhi":  "data/processed/uhi/uhi_intensity_{y}.tif",
}
VAR_LABELS = {
    "lst": "°C", "ndvi": "NDVI (−1 to 1)",
    "ndbi": "NDBI (−1 to 1)", "uhi": "°C above rural reference",
}
VAR_CMAPS = {
    "lst": "inferno", "ndvi": "RdYlGn",
    "ndbi": "YlOrRd", "uhi": "YlOrRd",
}

available_years = [
    y for y in YEARS
    if pp(VAR_PATHS[variable], y=y).exists()
]

temporal_dir = PROJECT_ROOT / "data/processed/temporal"
table_dir    = PROJECT_ROOT / "data/processed/tables"
maps_dir     = PROJECT_ROOT / "outputs/maps"

# ── Check data available ──────────────────────────────────────────────────────
if len(available_years) < 2:
    st.markdown("---")
    st.warning(
        f"Only **{len(available_years)} year(s)** of `{variable}` data found. "
        "Need at least 2 to compute change maps."
    )
    st.markdown(
        "Run the full pipeline for each year:\n"
        "```\n"
        "make lst    # then set year=2015, 2020\n"
        "make indices\n"
        "# then run temporal comparison:\n"
        "python scripts/10_temporal_comparison.py --variable " + variable + "\n"
        "```"
    )
    st.stop()

st.sidebar.success(f"✅ {len(available_years)} year(s) available: {', '.join(str(y) for y in available_years)}")
st.markdown("---")

# ── Tab layout ────────────────────────────────────────────────────────────────
tab_years, tab_change, tab_trend, tab_lga = st.tabs(
    ["Annual Maps", "Change Maps", "Trend Direction", "LGA Summary"]
)

# ── Tab 1: Annual raster maps ─────────────────────────────────────────────────
with tab_years:
    st.subheader(f"{variable.upper()} Maps — {', '.join(str(y) for y in available_years)}")
    cols = st.columns(len(available_years), gap="medium")
    all_arrays = {}
    for col, yr in zip(cols, available_years):
        with col:
            arr, prof, _ = load_raster(str(pp(VAR_PATHS[variable], y=yr)))
            if arr is None:
                st.warning(f"{yr}: not found")
                continue
            all_arrays[yr] = (arr, prof)
            fig = render_raster_map(
                arr, prof,
                title=f"{variable.upper()} — {yr}",
                cmap=VAR_CMAPS[variable],
                label=VAR_LABELS[variable],
                lgas=lgas,
                figsize=(5, 5),
                annotate_lgas=False,
            )
            st.pyplot(fig, use_container_width=True)
            import matplotlib.pyplot as plt; plt.close(fig)
            valid = arr[np.isfinite(arr)]
            st.caption(f"Mean: {float(valid.mean()):.2f}  ·  Max: {float(valid.max()):.2f}")

# ── Tab 2: Change maps ────────────────────────────────────────────────────────
with tab_change:
    change_pairs = list(zip(available_years[:-1], available_years[1:]))
    if len(available_years) >= 3:
        change_pairs.append((available_years[0], available_years[-1]))

    change_maps_found = []
    for y_early, y_late in change_pairs:
        path = temporal_dir / f"{variable}_change_{y_early}_{y_late}.tif"
        if path.exists():
            change_maps_found.append((y_early, y_late, path))

    if not change_maps_found:
        no_data(
            f"{variable}_change_{available_years[0]}_{available_years[-1]}.tif",
            f"python scripts/10_temporal_comparison.py --variable {variable} --years 2015 2023 2025",
        )
    else:
        n = len(change_maps_found)
        cols = st.columns(n, gap="medium")
        for col, (y_early, y_late, path) in zip(cols, change_maps_found):
            with col:
                png_path = maps_dir / f"{variable}_change_{y_early}_{y_late}.png"
                arr, prof, _ = load_raster(str(path))
                if arr is None:
                    continue
                valid = arr[np.isfinite(arr)]
                if png_path.exists():
                    st.image(
                        str(png_path),
                        caption=str(png_path.relative_to(PROJECT_ROOT)),
                        use_container_width=True,
                    )
                    if valid.size:
                        st.caption(f"Mean change: {float(valid.mean()):+.3f}")
                    continue
                vabs = float(np.percentile(np.abs(valid), 98)) if valid.size else 1
                fig = render_raster_map(
                    arr, prof,
                    title=f"Δ {variable.upper()} ({y_early}→{y_late})",
                    cmap="RdBu_r",
                    label=f"Δ {VAR_LABELS[variable]}",
                    vmin=-vabs, vmax=vabs,
                    lgas=lgas,
                    figsize=(5, 5),
                    annotate_lgas=False,
                )
                st.pyplot(fig, use_container_width=True)
                import matplotlib.pyplot as plt; plt.close(fig)
                pos_pct = float((valid > 0).mean() * 100)
                direction = "↑ warming/increasing" if variable in ("lst","ndbi","uhi") else "↑ greening"
                st.caption(
                    f"Mean Δ: {float(valid.mean()):+.3f}  ·  "
                    f"{pos_pct:.0f}% pixels {direction if valid.mean() > 0 else '↓'}"
                )

        # Distribution of change values
        st.markdown("---")
        st.subheader("Change Distribution")
        hist_data = []
        for y_early, y_late, path in change_maps_found:
            arr, _, _ = load_raster(str(path))
            if arr is None:
                continue
            valid = arr[np.isfinite(arr)]
            sample = valid[::max(1, len(valid)//3000)]
            for v in sample:
                hist_data.append({"Period": f"{y_early}→{y_late}", "Change": float(v)})

        if hist_data:
            hist_df = pd.DataFrame(hist_data)
            fig_hist = px.histogram(
                hist_df, x="Change", color="Period", barmode="overlay",
                nbins=60, opacity=0.7,
                title=f"{variable.upper()} Change Distribution by Period",
                template="plotly_dark",
                labels={"Change": f"Δ {VAR_LABELS[variable]}"},
            )
            fig_hist.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.6)
            fig_hist.update_layout(margin=dict(t=50, b=10))
            st.plotly_chart(fig_hist, use_container_width=True)

# ── Tab 3: Trend direction ────────────────────────────────────────────────────
with tab_trend:
    tau_path   = temporal_dir / f"{variable}_trend_tau.tif"
    slope_path = temporal_dir / f"{variable}_trend_slope_per_year.tif"

    if not tau_path.exists():
        no_data(
            f"{variable}_trend_tau.tif",
            f"python scripts/10_temporal_comparison.py --variable {variable} --years 2015 2023 2025",
        )
    else:
        col_tau, col_slope = st.columns(2, gap="medium")

        with col_tau:
            arr, prof, _ = load_raster(str(tau_path))
            if arr is not None:
                tau_png = maps_dir / f"{variable}_trend_tau.png"
                if tau_png.exists():
                    st.image(
                        str(tau_png),
                        caption=str(tau_png.relative_to(PROJECT_ROOT)),
                        use_container_width=True,
                    )
                fig = render_raster_map(
                    arr, prof,
                    title=f"Mann-Kendall Tau — {variable.upper()}",
                    cmap="RdBu_r",
                    label="Kendall's Tau (−1 to +1)",
                    vmin=-1, vmax=1,
                    lgas=lgas, figsize=(6, 6),
                )
                st.pyplot(fig, use_container_width=True)
                import matplotlib.pyplot as plt; plt.close(fig)

                valid_tau = arr[np.isfinite(arr)]
                pos_pct = float((valid_tau > 0).mean() * 100)
                neg_pct = float((valid_tau < 0).mean() * 100)
                st.caption(
                    f"Tau > 0 (increasing): **{pos_pct:.0f}%** of study area  ·  "
                    f"Tau < 0 (decreasing): **{neg_pct:.0f}%**"
                )
                if len(available_years) < 8:
                    st.info(
                        f"ℹ️ With {len(available_years)} time points, Tau = ±1 means a "
                        "perfectly monotonic trend. P-values are not reliable at this "
                        "sample size — use Tau as a trend direction indicator only.",
                        icon="ℹ️",
                    )

        with col_slope:
            if slope_path.exists():
                arr2, prof2, _ = load_raster(str(slope_path))
                if arr2 is not None:
                    valid2 = arr2[np.isfinite(arr2)]
                    slope_png = maps_dir / f"{variable}_trend_slope_per_year.png"
                    if slope_png.exists():
                        st.image(
                            str(slope_png),
                            caption=str(slope_png.relative_to(PROJECT_ROOT)),
                            use_container_width=True,
                        )
                    vabs = float(np.percentile(np.abs(valid2), 98)) if valid2.size else 1
                    fig2 = render_raster_map(
                        arr2, prof2,
                        title=f"Linear Trend Slope — {variable.upper()}",
                        cmap="RdBu_r",
                        label=f"{VAR_LABELS[variable]} / year",
                        vmin=-vabs, vmax=vabs,
                        lgas=lgas, figsize=(6, 6),
                    )
                    st.pyplot(fig2, use_container_width=True)
                    import matplotlib.pyplot as plt; plt.close(fig2)
                    st.caption(
                        f"Mean slope: {float(valid2.mean()):+.4f} units/year  ·  "
                        f"Max warming rate: {float(valid2.max()):+.4f}"
                    )

# ── Tab 4: LGA summary ────────────────────────────────────────────────────────
with tab_lga:
    lga_table_path = table_dir / f"temporal_lga_summary_{variable}.csv"
    lga_df = load_csv(str(lga_table_path))

    if lga_df is None:
        no_data(
            f"temporal_lga_summary_{variable}.csv",
            f"python scripts/10_temporal_comparison.py --variable {variable}",
        )
    else:
        st.markdown(f"**LGA-level {variable.upper()} Statistics by Year**")

        # Line chart: mean value over time per LGA
        mean_cols = [c for c in lga_df.columns if c.startswith("mean_")]
        if mean_cols and "lga_name" in lga_df.columns:
            melted = lga_df.melt(
                id_vars=["lga_name"],
                value_vars=mean_cols,
                var_name="Year", value_name=f"Mean {variable.upper()}",
            )
            melted["Year"] = melted["Year"].str.replace("mean_", "").astype(int)

            fig_line = px.line(
                melted, x="Year", y=f"Mean {variable.upper()}", color="lga_name",
                title=f"Mean {variable.upper()} per LGA over Time",
                template="plotly_dark",
                markers=True,
                labels={"lga_name": "LGA", "Year": "Year"},
            )
            fig_line.update_layout(
                margin=dict(t=50, b=10),
                legend=dict(orientation="v", x=1.02, y=1),
            )
            st.plotly_chart(fig_line, use_container_width=True)

        # Full table
        st.markdown("**Full LGA Summary Table**")
        styled_cols = {c: c.replace("_", " ").title() for c in lga_df.columns}
        st.dataframe(
            lga_df.rename(columns=styled_cols),
            use_container_width=True, hide_index=True,
        )

        # Change ranking bar chart
        change_cols = [c for c in lga_df.columns if c.startswith("change_")]
        if change_cols and "lga_name" in lga_df.columns:
            selected_change = st.selectbox("Show change for period:", change_cols)
            change_df = lga_df[["lga_name", selected_change]].dropna()
            change_df = change_df.sort_values(selected_change, ascending=False)
            fig_chg = go.Figure(go.Bar(
                x=change_df["lga_name"],
                y=change_df[selected_change],
                marker_color=[
                    "#E05252" if v > 0 else "#4A90D9"
                    for v in change_df[selected_change]
                ],
                text=change_df[selected_change].round(3),
                textposition="outside",
            ))
            fig_chg.update_layout(
                title=f"{variable.upper()} Change ({selected_change.replace('change_','').replace('_',' → ')}) by LGA",
                template="plotly_dark",
                xaxis_tickangle=-35,
                yaxis_title=f"Δ {VAR_LABELS[variable]}",
                showlegend=False,
                margin=dict(t=50, b=70),
            )
            fig_chg.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
            st.plotly_chart(fig_chg, use_container_width=True)
