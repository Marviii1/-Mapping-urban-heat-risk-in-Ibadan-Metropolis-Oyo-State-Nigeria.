"""UHI Intensity, LISA Clusters, and Gi* Hot Spot Explorer."""
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
    load_raster, load_vector, load_csv, render_raster_map,
    render_vector_map, no_data, sidebar_year,
)


def report_stat(year: int, layer: str) -> dict[str, float] | None:
    """Read summary statistics from the committed markdown report."""
    stats_csv = PROJECT_ROOT / f"outputs/tables/dashboard_summary_stats_{year}.csv"
    if stats_csv.exists():
        stats_df = pd.read_csv(stats_csv)
        match = stats_df[stats_df["layer"].astype(str).str.lower() == layer.lower()]
        if not match.empty:
            return match.iloc[0].to_dict()

    report = PROJECT_ROOT / f"outputs/reports/ibadan_heat_risk_summary_{year}.md"
    if not report.exists():
        return None
    in_table = False
    for raw in report.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("| Layer |"):
            in_table = True
            continue
        if in_table and (not line or not line.startswith("|")):
            break
        if not in_table or line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) >= 5 and parts[0].lower() == layer.lower():
            try:
                return {
                    "layer": parts[0],
                    "min": float(parts[1]),
                    "mean": float(parts[2]),
                    "max": float(parts[3]),
                    "std": float(parts[4]),
                }
            except ValueError:
                return None
    return None


def normalise_lisa_cluster(series: pd.Series) -> pd.Series:
    """Return LISA cluster labels as HH, LL, HL, LH, or NS."""
    cleaned = series.fillna("NS").astype(str).str.upper().str.strip()
    return cleaned.replace({
        "HIGH-HIGH": "HH",
        "HOT-HOT": "HH",
        "LOW-LOW": "LL",
        "COLD-COLD": "LL",
        "HIGH-LOW": "HL",
        "HOT-COLD": "HL",
        "LOW-HIGH": "LH",
        "COLD-HOT": "LH",
        "NOT SIGNIFICANT": "NS",
        "NOT_SIGNIFICANT": "NS",
        "NAN": "NS",
        "NONE": "NS",
        "0": "NS",
    })


def normalise_gistar_class(series: pd.Series) -> pd.Series:
    """Return Gi* class labels in the dashboard's canonical snake-case form."""
    cleaned = series.fillna("not_significant").astype(str).str.lower().str.strip()
    cleaned = cleaned.str.replace(" ", "_", regex=False).str.replace("-", "_", regex=False)
    return cleaned.replace({
        "nan": "not_significant",
        "none": "not_significant",
        "0": "not_significant",
    })

st.set_page_config(page_title="UHI & Hotspots", page_icon="🔥", layout="wide")
st.title("🔥 Urban Heat Island & Hot Spot Analysis")
st.caption(
    "UHI Intensity = pixel LST − mean rural-reference LST · "
    "Spatial clusters via LISA (Local Moran's I) and Getis-Ord Gi*"
)

year = sidebar_year()
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**UHI Classes**\n"
    "- 1 · Very Low  ≤ 0 °C\n"
    "- 2 · Low       0–2 °C\n"
    "- 3 · Moderate  2–4 °C\n"
    "- 4 · High      4–6 °C\n"
    "- 5 · Very High > 6 °C\n"
)

# ── Load UHI raster ───────────────────────────────────────────────────────────
uhi_path  = pp("data/processed/uhi/uhi_intensity_{y}.tif", y=year)
cls_path  = pp("data/processed/uhi/uhi_classes_{y}.tif",   y=year)
lisa_path = pp("data/processed/esda/lisa_clusters_{y}.gpkg", y=year)
gi_path   = pp("data/processed/esda/gistar_hotspots_{y}.gpkg", y=year)
moran_path = pp("data/processed/esda/morans_i_{y}.csv", y=year)

uhi_arr, uhi_profile, _ = load_raster(str(uhi_path))
lgas = load_vector(str(LGAS_PATH))

if uhi_arr is None:
    web_maps = [
        ("UHI Intensity", pp("outputs/maps/uhi_{y}.png", y=year)),
        ("UHI Classes", pp("outputs/maps/uhi_classes_{y}.png", y=year)),
        ("LISA Clusters", pp("outputs/maps/lisa_clusters_{y}.png", y=year)),
        ("Gi* Hotspots", pp("outputs/maps/gistar_hotspots_{y}.png", y=year)),
    ]
    web_maps = [(label, path) for label, path in web_maps if path.exists()]
    moran_web = pp("outputs/tables/morans_i_{y}.csv", y=year)
    urban_rural_web = pp("outputs/tables/urban_rural_lst_{y}.csv", y=year)
    if web_maps or moran_web.exists() or urban_rural_web.exists():
        st.markdown("---")
        stats = report_stat(year, "Urban Heat Island Intensity")
        class_df_web = load_csv(str(pp("outputs/tables/uhi_class_distribution_{y}.csv", y=year)))
        if stats:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Min UHI", f"{stats['min']:.2f} °C")
            c2.metric("Max UHI", f"{stats['max']:.2f} °C")
            c3.metric("Mean UHI", f"{stats['mean']:.2f} °C")
            if class_df_web is not None and "class_code" in class_df_web.columns:
                pct_high = float(class_df_web.loc[class_df_web["class_code"].isin([4, 5]), "pct_area"].sum())
                pct_very_high = float(class_df_web.loc[class_df_web["class_code"] == 5, "pct_area"].sum())
                c4.metric("% High / Very High", f"{pct_high:.1f}%")
                c5.metric("% Very High (>6°C)", f"{pct_very_high:.1f}%")
            else:
                c4.metric("Std Dev", f"{stats['std']:.2f} °C")
                c5.metric("Map Source", "PNG")
            st.markdown("---")
        if web_maps:
            tab_labels = ["UHI Intensity", "UHI Classes", "LISA Clusters", "Gi* Hotspots"]
            tabs = st.tabs(tab_labels)
            map_lookup = {label: path for label, path in web_maps}
            with tabs[0]:
                col_map, col_right = st.columns([3, 2], gap="large")
                with col_map:
                    path = map_lookup.get("UHI Intensity")
                    if path:
                        st.image(str(path), caption=str(path.relative_to(PROJECT_ROOT)), use_container_width=True)
                with col_right:
                    if class_df_web is not None:
                        pie_df = class_df_web[class_df_web["pixel_count"] > 0].copy()
                        fig_pie = px.pie(
                            pie_df,
                            names="label",
                            values="pct_area",
                            title=f"UHI Class Area Distribution ({year})",
                            template="plotly_dark",
                        )
                        fig_pie.update_traces(textinfo="percent+label", textfont_size=11)
                        fig_pie.update_layout(showlegend=False, margin=dict(t=50, b=10))
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Run `python scripts/12_export_dashboard_metrics.py` locally to add UHI class distribution tables to cloud.")
            with tabs[1]:
                col_map, col_table = st.columns([3, 2], gap="large")
                with col_map:
                    path = map_lookup.get("UHI Classes")
                    if path:
                        st.image(str(path), caption=str(path.relative_to(PROJECT_ROOT)), use_container_width=True)
                with col_table:
                    if class_df_web is not None:
                        fig_bar = px.bar(
                            class_df_web,
                            x="label",
                            y="pct_area",
                            color="label",
                            title=f"UHI Class Area Statistics ({year})",
                            template="plotly_dark",
                            text="pct_area",
                            color_discrete_sequence=["#2166AC", "#92C5DE", "#FEE08B", "#F46D43", "#A50026"],
                        )
                        fig_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                        fig_bar.update_layout(showlegend=False, xaxis_title="Class", yaxis_title="% Area")
                        st.plotly_chart(fig_bar, use_container_width=True)
                        st.dataframe(class_df_web, use_container_width=True, hide_index=True)
            with tabs[2]:
                path = map_lookup.get("LISA Clusters")
                if path:
                    st.image(str(path), caption=str(path.relative_to(PROJECT_ROOT)), use_container_width=True)
            with tabs[3]:
                path = map_lookup.get("Gi* Hotspots")
                if path:
                    st.image(str(path), caption=str(path.relative_to(PROJECT_ROOT)), use_container_width=True)
        st.markdown("---")
        st.subheader("UHI and Spatial Statistics Tables")
        for label, path in {"Global Moran's I": moran_web, "Urban-rural LST summary": urban_rural_web}.items():
            df = load_csv(str(path))
            with st.expander(label, expanded=True):
                if df is not None:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{path.name} is not available.")
        st.stop()

    st.markdown("---")
    no_data(
        f"uhi_intensity_{year}.tif",
        f"python scripts/05_compute_uhi_intensity.py --year {year} --reference auto",
    )
    st.stop()

valid = uhi_arr[np.isfinite(uhi_arr)]

# ── UHI class computation ─────────────────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
from src.uhi.classification import (
    classify_uhi_with_stats, UHI_CLASS_LABELS, UHI_CLASS_COLOURS,
)
classes, class_df = classify_uhi_with_stats(uhi_arr)

# ── Summary metrics ───────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Min UHI", f"{float(valid.min()):.2f} °C")
c2.metric("Max UHI", f"{float(valid.max()):.2f} °C")
c3.metric("Mean UHI", f"{float(valid.mean()):.2f} °C")

pct_high = float(class_df.loc[class_df["class_code"].isin([4, 5]), "pct_area"].sum())
pct_very_high = float(class_df.loc[class_df["class_code"] == 5, "pct_area"].sum())
c4.metric("% High / Very High", f"{pct_high:.1f}%")
c5.metric("% Very High (>6°C)", f"{pct_very_high:.1f}%")
st.markdown("---")

# ── Maps row ──────────────────────────────────────────────────────────────────
tab_uhi, tab_class, tab_lisa, tab_gi = st.tabs(
    ["UHI Intensity", "UHI Classes", "LISA Clusters", "Gi* Hotspots"]
)

with tab_uhi:
    col_map, col_right = st.columns([3, 2], gap="large")
    with col_map:
        fig = render_raster_map(
            uhi_arr, uhi_profile,
            title=f"UHI Intensity — Ibadan {year}",
            cmap="YlOrRd", label="°C above rural reference",
            lgas=lgas, figsize=(8, 7),
        )
        st.pyplot(fig, use_container_width=True)
        import matplotlib.pyplot as plt; plt.close(fig)

    with col_right:
        # Class distribution pie chart
        pie_df = class_df[class_df["pixel_count"] > 0].copy()
        pie_df["label"] = pie_df["class_code"].map(UHI_CLASS_LABELS)
        colours_list = [UHI_CLASS_COLOURS[c] for c in pie_df["class_code"]]

        fig_pie = px.pie(
            pie_df, names="label", values="pct_area",
            color="label",
            color_discrete_map={UHI_CLASS_LABELS[c]: UHI_CLASS_COLOURS[c]
                                for c in UHI_CLASS_COLOURS},
            title=f"UHI Class Area Distribution ({year})",
            template="plotly_dark",
        )
        fig_pie.update_traces(textinfo="percent+label", textfont_size=11)
        fig_pie.update_layout(showlegend=False, margin=dict(t=50, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

        # Class stats table
        display_df = class_df[["class_code", "label", "area_km2", "pct_area",
                                "mean_uhi_celsius", "max_uhi_celsius"]].copy()
        display_df.columns = ["Code", "Class", "Area (km²)", "% Area",
                               "Mean UHI (°C)", "Max UHI (°C)"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

with tab_class:
    if cls_path.exists():
        cls_arr, cls_profile, _ = load_raster(str(cls_path))
        if cls_arr is not None:
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
            import matplotlib.patches as mpatches

            cmap_uhi = mcolors.ListedColormap(
                [UHI_CLASS_COLOURS[i] for i in sorted(UHI_CLASS_COLOURS)]
            )
            bounds_cmap = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
            norm = mcolors.BoundaryNorm(bounds_cmap, cmap_uhi.N)

            from rasterio.transform import array_bounds
            tr = cls_profile["transform"]
            h, w = cls_arr.shape
            left, bottom, right, top = array_bounds(h, w, tr)
            extent = [left, right, bottom, top]

            fig, ax = plt.subplots(figsize=(8, 7), dpi=110)
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")
            ax.imshow(cls_arr, cmap=cmap_uhi, norm=norm, extent=extent,
                      interpolation="nearest", aspect="equal")
            if lgas is not None:
                lgas.boundary.plot(ax=ax, edgecolor="#111111", linewidth=0.6, alpha=0.75)
            patches = [mpatches.Patch(color=UHI_CLASS_COLOURS[c], label=f"{c} — {UHI_CLASS_LABELS[c]}")
                       for c in sorted(UHI_CLASS_COLOURS)]
            ax.legend(handles=patches, loc="lower right", facecolor="white",
                      labelcolor="#111111", fontsize=10, framealpha=0.9)
            ax.set_title(f"UHI Thermal Classes — Ibadan {year}", color="#111111", fontsize=15, fontweight="bold")
            ax.set_axis_off()
            fig.tight_layout(pad=0.4)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
    else:
        # Generate on the fly from UHI raster
        st.info("UHI classes raster not saved separately — showing derived classification from UHI intensity.")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        import matplotlib.patches as mpatches
        from rasterio.transform import array_bounds

        cmap_uhi = mcolors.ListedColormap(
            [UHI_CLASS_COLOURS[i] for i in sorted(UHI_CLASS_COLOURS)]
        )
        norm = mcolors.BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5, 5.5], cmap_uhi.N)
        tr = uhi_profile["transform"]
        h, w = classes.shape
        left, bottom, right, top = array_bounds(h, w, tr)
        fig, ax = plt.subplots(figsize=(8, 7), dpi=110)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.imshow(
            classes,
            cmap=cmap_uhi,
            norm=norm,
            extent=[left, right, bottom, top],
            interpolation="nearest",
            aspect="equal",
        )
        if lgas is not None:
            lgas.boundary.plot(ax=ax, edgecolor="#111111", linewidth=0.6, alpha=0.75)
        patches = [
            mpatches.Patch(color=UHI_CLASS_COLOURS[c], label=f"{c} - {UHI_CLASS_LABELS[c]}")
            for c in sorted(UHI_CLASS_COLOURS)
        ]
        ax.legend(handles=patches, loc="lower right", facecolor="white",
                  labelcolor="#111111", fontsize=10, framealpha=0.9)
        ax.set_title(f"UHI Thermal Classes - Ibadan {year}", color="#111111", fontsize=15, fontweight="bold")
        ax.set_axis_off()
        fig.tight_layout(pad=0.4)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    st.markdown("**UHI Class Area Statistics**")
    class_stats = class_df[["class_code", "label", "area_km2", "pct_area",
                            "mean_uhi_celsius", "max_uhi_celsius"]].copy()
    class_stats.columns = ["Code", "Class", "Area (km2)", "% Area",
                           "Mean UHI (deg C)", "Max UHI (deg C)"]
    st.dataframe(class_stats, use_container_width=True, hide_index=True)

with tab_lisa:
    lisa_gdf = load_vector(str(lisa_path))
    if lisa_gdf is None:
        no_data(f"lisa_clusters_{year}.gpkg",
                f"python scripts/06_run_esda.py --target lst --year {year}")
    else:
        col_map2, col_stats2 = st.columns([3, 2], gap="large")
        with col_map2:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches

            LISA_COLOURS = {
                "HH": "#d7191c", "LL": "#2c7bb6",
                "HL": "#fdae61", "LH": "#abd9e9", "NS": "#cccccc",
            }
            fig, ax = plt.subplots(figsize=(8, 7), dpi=110)
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")

            cluster_col = next(
                (c for c in lisa_gdf.columns if "cluster" in c.lower() or "lisa" in c.lower()),
                None,
            )
            if cluster_col:
                lisa_clusters = normalise_lisa_cluster(lisa_gdf[cluster_col])
                for cluster_type, colour in LISA_COLOURS.items():
                    subset = lisa_gdf[lisa_clusters == cluster_type]
                    if not subset.empty:
                        subset.plot(ax=ax, facecolor=colour, edgecolor="none", alpha=0.85)

            if lgas is not None:
                lgas.to_crs(lisa_gdf.crs).boundary.plot(
                    ax=ax, edgecolor="#111111", linewidth=0.8, alpha=0.75
                )
            patches = [mpatches.Patch(color=c, label=f"{t} — {'Hot-Hot' if t=='HH' else 'Cold-Cold' if t=='LL' else 'Hot outlier' if t=='HL' else 'Cold outlier' if t=='LH' else 'Not significant'}")
                       for t, c in LISA_COLOURS.items()]
            ax.legend(handles=patches, loc="lower right", facecolor="white",
                      labelcolor="#111111", fontsize=9.5, framealpha=0.9)
            ax.set_title(f"LISA Cluster Map — Ibadan {year}", color="#111111", fontsize=15, fontweight="bold")
            ax.set_axis_off()
            fig.tight_layout(pad=0.4)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        with col_stats2:
            st.markdown("**LISA Cluster Counts**")
            if cluster_col:
                lisa_clusters = normalise_lisa_cluster(lisa_gdf[cluster_col])
                counts = (
                    lisa_clusters
                    .value_counts().reset_index()
                )
                counts.columns = ["Cluster", "Count"]
                label_map = {"HH": "Hot-Hot", "LL": "Cold-Cold",
                             "HL": "Hot outlier", "LH": "Cold outlier", "NS": "Not significant"}
                counts["Type"] = counts["Cluster"].map(label_map)
                colour_list = [LISA_COLOURS.get(c, "#888") for c in counts["Cluster"]]
                fig_bar = px.bar(counts, x="Cluster", y="Count",
                                 color="Cluster",
                                 color_discrete_map=LISA_COLOURS,
                                 title="LISA Cluster Distribution",
                                 template="plotly_dark",
                                 text="Count")
                fig_bar.update_traces(textposition="outside")
                fig_bar.update_layout(showlegend=False, margin=dict(t=50, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)
                st.dataframe(counts[["Cluster", "Type", "Count"]],
                             use_container_width=True, hide_index=True)

            # Moran's I result
            moran_df = None
            if moran_path.exists():
                import pandas as _pd
                moran_df = _pd.read_csv(str(moran_path))
            if moran_df is not None:
                st.markdown("**Global Moran's I**")
                st.dataframe(moran_df, use_container_width=True, hide_index=True)

with tab_gi:
    gi_gdf = load_vector(str(gi_path))
    if gi_gdf is None:
        no_data(f"gistar_hotspots_{year}.gpkg",
                f"python scripts/06_run_esda.py --target lst --year {year}")
    else:
        col_map3, col_stats3 = st.columns([3, 2], gap="large")
        with col_map3:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches

            GI_COLOURS = {
                "hot_spot_99": "#a50026", "hot_spot_95": "#d73027",
                "hot_spot_90": "#f46d43", "not_significant": "#cccccc",
                "cold_spot_90": "#74add1", "cold_spot_95": "#4575b4",
                "cold_spot_99": "#313695",
            }
            fig, ax = plt.subplots(figsize=(8, 7), dpi=110)
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")

            sig_col = next(
                (c for c in gi_gdf.columns
                 if any(k in c.lower() for k in ["significant", "hotspot", "gi_class", "class"])),
                None,
            )
            zscore_col = next(
                (c for c in gi_gdf.columns if "zscore" in c.lower() or "z_score" in c.lower()),
                None,
            )

            if sig_col:
                gi_classes = normalise_gistar_class(gi_gdf[sig_col])
                for stype, colour in GI_COLOURS.items():
                    subset = gi_gdf[gi_classes == stype]
                    if not subset.empty:
                        subset.plot(ax=ax, facecolor=colour, edgecolor="none", alpha=0.85)
            elif zscore_col:
                # Fallback: colour by z-score magnitude
                gi_gdf.plot(column=zscore_col, cmap="RdBu_r", ax=ax,
                            legend=True, alpha=0.85)

            if lgas is not None:
                lgas.to_crs(gi_gdf.crs).boundary.plot(
                    ax=ax, edgecolor="#111111", linewidth=0.8, alpha=0.75
                )
            ax.set_title(f"Getis-Ord Gi* Hot/Cold Spots — {year}",
                         color="#111111", fontsize=15, fontweight="bold")
            ax.set_axis_off()
            fig.tight_layout(pad=0.4)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        with col_stats3:
            st.markdown("**Gi* Dataset**")
            display_cols = [c for c in gi_gdf.columns if c != "geometry"][:8]
            st.dataframe(gi_gdf[display_cols].head(20),
                         use_container_width=True, hide_index=True)

            if zscore_col:
                fig_hist = px.histogram(
                    gi_gdf, x=zscore_col, nbins=40,
                    title="Gi* Z-score Distribution",
                    template="plotly_dark",
                    color_discrete_sequence=["#E05252"],
                    labels={zscore_col: "Gi* Z-score"},
                )
                fig_hist.add_vline(x=1.645, line_dash="dash", line_color="#FEE08B",
                                   annotation_text="90%", annotation_font_color="#FEE08B")
                fig_hist.add_vline(x=1.96, line_dash="dash", line_color="#FDAE61",
                                   annotation_text="95%", annotation_font_color="#FDAE61")
                fig_hist.update_layout(margin=dict(t=50, b=10))
                st.plotly_chart(fig_hist, use_container_width=True)
