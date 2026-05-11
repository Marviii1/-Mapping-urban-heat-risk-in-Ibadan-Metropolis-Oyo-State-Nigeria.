"""Shared helpers for the Ibadan Heat Risk Streamlit dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

WEB_LGAS_PATH = PROJECT_ROOT / "app/assets/ibadan_lgas.geojson"
WEB_BOUNDARY_PATH = PROJECT_ROOT / "app/assets/ibadan_metropolitan_boundary.geojson"
LOCAL_LGAS_PATH = PROJECT_ROOT / "data/processed/uhi/ibadan_lgas.gpkg"
LOCAL_BOUNDARY_PATH = PROJECT_ROOT / "data/processed/uhi/ibadan_metropolitan_boundary.gpkg"
LGAS_PATH = LOCAL_LGAS_PATH if LOCAL_LGAS_PATH.exists() else WEB_LGAS_PATH
BOUNDARY_PATH = LOCAL_BOUNDARY_PATH if LOCAL_BOUNDARY_PATH.exists() else WEB_BOUNDARY_PATH
YEARS = [2025, 2023, 2015]


def existing_path(*candidates: Path) -> Path:
    """Return the first existing path, falling back to the first candidate."""
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def apply_dashboard_style() -> None:
    """Apply a cohesive mid-dark Streamlit theme across all dashboard pages."""
    st.markdown(
        """
        <style>
        :root {
            --bg: #0B1320;
            --panel: #111C2F;
            --panel-2: #1A2940;
            --line: rgba(255, 255, 255, 0.14);
            --text: #FFFFFF;
            --muted: #D8E2EF;
            --accent: #F97316;
            --accent-2: #38BDF8;
        }
        .stApp {
            background: linear-gradient(180deg, #07101D 0%, #0B1320 46%, #101A2A 100%);
            color: var(--text);
        }
        [data-testid="stSidebar"] {
            background: #08111F;
            border-right: 1px solid var(--line);
            padding-top: 1rem;
        }
        [data-testid="stSidebar"] * {
            color: var(--text);
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] li {
            color: #FFFFFF;
            line-height: 1.65;
            font-size: 1.08rem;
        }
        [data-testid="stSidebar"] a {
            color: #38BDF8 !important;
            font-size: 1.06rem;
            font-weight: 700;
            text-decoration: none;
        }
        .block-container {
            max-width: 1540px;
            padding-top: 3rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3 {
            color: #FFFFFF;
            letter-spacing: 0;
        }
        h1 {
            font-size: 3.35rem;
            line-height: 1.15;
            margin-bottom: 0.85rem;
        }
        h2 {
            font-size: 2.2rem;
        }
        h3 {
            font-size: 1.55rem;
        }
        p, li, label, .stCaption, [data-testid="stMarkdownContainer"] {
            color: #FFFFFF;
            font-size: 1.14rem;
            line-height: 1.65;
        }
        [data-testid="stCaptionContainer"] {
            color: #D8E2EF;
            font-size: 1.08rem;
        }
        hr {
            border-color: var(--line);
            margin: 1.6rem 0;
        }
        [data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(26, 41, 64, 0.98), rgba(17, 28, 47, 0.98));
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1.15rem 1.15rem 1rem;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
            min-height: 138px;
        }
        [data-testid="stMetricLabel"] p {
            color: #FFFFFF;
            font-size: 1.22rem !important;
            font-weight: 900 !important;
        }
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] div {
            color: #FFFFFF;
            font-size: 2.85rem !important;
            font-weight: 950 !important;
            line-height: 1.08 !important;
        }
        [data-testid="stMetricDelta"] span,
        [data-testid="stMetricDelta"] svg {
            font-size: 1.18rem !important;
            font-weight: 800;
        }
        [data-testid="stMetricDelta"] {
            color: #7DD3FC;
        }
        div[data-testid="stTabs"] button {
            color: #FFFFFF;
            font-weight: 600;
            font-size: 1.2rem;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #FFFFFF;
            border-bottom-color: var(--accent);
        }
        [data-testid="stDataFrame"],
        [data-testid="stTable"],
        .stPlotlyChart,
        [data-testid="stImage"],
        iframe {
            background: rgba(8, 17, 31, 0.82);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.55rem;
        }
        .stAlert {
            border-radius: 8px;
        }
        [data-testid="stSidebarNav"] a,
        [data-testid="stSidebarNav"] span,
        [data-testid="stSidebarNav"] p {
            font-size: 1.16rem !important;
            font-weight: 900 !important;
            color: #FFFFFF !important;
            letter-spacing: 0;
        }
        [data-testid="stSidebarNav"] a {
            border-radius: 7px;
            padding-top: 0.42rem !important;
            padding-bottom: 0.42rem !important;
        }
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] div,
        [data-baseweb="select"] div {
            font-size: 1.12rem !important;
            font-weight: 850 !important;
            color: #FFFFFF !important;
        }
        [data-baseweb="select"] > div {
            background: rgba(8, 17, 31, 0.9) !important;
            border: 1.5px solid rgba(255, 255, 255, 0.82) !important;
            border-radius: 8px !important;
            min-height: 46px !important;
            box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.22);
        }
        [data-baseweb="popover"] {
            font-size: 1.08rem !important;
        }
        [data-testid="stDataFrame"] * {
            font-size: 1rem !important;
            color: #FFFFFF !important;
        }
        code, pre {
            border-radius: 6px !important;
            font-size: 1rem !important;
        }
        .artifact-card {
            background: linear-gradient(180deg, rgba(26, 41, 64, 0.98), rgba(13, 23, 38, 0.98));
            border: 1px solid var(--line);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 1.15rem;
            min-height: 150px;
        }
        .artifact-card h3 {
            margin: 0 0 0.45rem;
        }
        .artifact-card p {
            margin: 0.25rem 0;
            line-height: 1.55;
            color: #FFFFFF;
        }
        .map-shell {
            background: linear-gradient(180deg, rgba(26, 41, 64, 0.98), rgba(8, 17, 31, 0.98));
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.85rem;
            box-shadow: 0 18px 38px rgba(0, 0, 0, 0.24);
        }
        .small-note {
            color: #D8E2EF;
            font-size: 1.14rem;
            line-height: 1.55;
        }
        .sidebar-brand {
            padding: 0.55rem 0 0.45rem;
        }
        .sidebar-brand-title {
            color: #FFFFFF;
            font-size: 1.62rem;
            font-weight: 900;
            line-height: 1.2;
            margin: 0.25rem 0 0.55rem;
        }
        .sidebar-subtitle {
            color: #FFFFFF;
            font-size: 1.02rem;
            font-style: italic;
            line-height: 1.45;
            margin-bottom: 1.2rem;
        }
        .sidebar-about-title {
            color: #FFFFFF;
            font-size: 1.18rem;
            font-weight: 900;
            margin-top: 1.1rem;
            margin-bottom: 0.65rem;
        }
        .github-link {
            display: inline-block;
            margin-top: 0.4rem;
            color: #38BDF8 !important;
            font-size: 1.08rem;
            font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def pp(template: str, **kw) -> Path:
    return PROJECT_ROOT / template.format(**kw)


def rel(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


@st.cache_data(show_spinner=False)
def load_raster(path_str: str):
    try:
        import rasterio

        with rasterio.open(path_str) as src:
            arr = src.read(1).astype("float32")
            if src.nodata is not None:
                arr[arr == src.nodata] = np.nan
            return arr, src.profile.copy(), src.bounds
    except Exception:
        return None, None, None


@st.cache_data(show_spinner=False)
def load_vector(path_str: str, layer=None):
    try:
        import geopandas as gpd

        return gpd.read_file(path_str, **({} if layer is None else {"layer": layer}))
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_csv(path_str: str):
    try:
        import pandas as pd

        return pd.read_csv(path_str)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_text(path_str: str):
    try:
        return Path(path_str).read_text(encoding="utf-8")
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_report_stats(year: int):
    """Read the report's raster statistics table as a small DataFrame."""
    import pandas as pd

    text = load_text(str(PROJECT_ROOT / f"outputs/reports/ibadan_heat_risk_summary_{year}.md"))
    if not text:
        return None

    records = []
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("| Layer |"):
            in_table = True
            continue
        if in_table and (not line or not line.startswith("|")):
            break
        if not in_table or line.startswith("|---"):
            continue

        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 5:
            continue
        layer, min_v, mean_v, max_v, std_v = parts
        try:
            records.append({
                "layer": layer,
                "min": float(min_v),
                "mean": float(mean_v),
                "max": float(max_v),
                "std": float(std_v),
            })
        except ValueError:
            continue

    return pd.DataFrame(records) if records else None


def stat_from_report(year: int, layer: str) -> dict[str, float] | None:
    """Return one layer's min/mean/max/std values from the markdown report."""
    stats = load_report_stats(year)
    if stats is None:
        return None
    match = stats[stats["layer"].str.lower() == layer.lower()]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


@st.cache_data(show_spinner=False)
def load_catalog(year: int):
    return load_csv(str(PROJECT_ROOT / f"outputs/catalog/output_catalog_{year}.csv"))


def file_status_table(year: int):
    import pandas as pd

    items = {
        "Ibadan LGAs": existing_path(LGAS_PATH, WEB_LGAS_PATH),
        "Metropolitan boundary": existing_path(BOUNDARY_PATH, WEB_BOUNDARY_PATH),
        "LST raster": pp("data/processed/lst/lst_ibadan_{y}_celsius.tif", y=year),
        "UHI intensity": pp("data/processed/uhi/uhi_intensity_{y}.tif", y=year),
        "LISA clusters": pp("data/processed/esda/lisa_clusters_{y}.gpkg", y=year),
        "Gi* hot spots": pp("data/processed/esda/gistar_hotspots_{y}.gpkg", y=year),
        "GWR results": pp("data/processed/gwr/gwr_results_{y}.gpkg", y=year),
        "GWR summary": pp("data/processed/gwr/gwr_summary_{y}.txt", y=year),
        "HVI raster": pp("data/processed/vulnerability/heat_vulnerability_index_{y}.tif", y=year),
        "HVI ranking": pp("data/processed/tables/ibadan_hvi_ranking_{y}.csv", y=year),
        "PDF report": pp("outputs/reports/ibadan_heat_risk_summary_{y}.pdf", y=year),
        "Output catalog": pp("outputs/catalog/output_catalog_{y}.csv", y=year),
    }
    return pd.DataFrame(
        [
            {
                "file": label,
                "available": path.exists(),
                "path": rel(path),
                "size_mb": round(path.stat().st_size / 1_000_000, 3) if path.exists() else None,
            }
            for label, path in items.items()
        ]
    )


def render_raster_map(
    arr: np.ndarray,
    profile,
    title: str = "",
    cmap: str = "inferno",
    label: str = "",
    vmin=None,
    vmax=None,
    figsize=(9, 7),
    lgas=None,
    annotate_lgas: bool = True,
):
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from rasterio.transform import array_bounds

    tr = profile["transform"]
    h, w = arr.shape
    left, bottom, right, top = array_bounds(h, w, tr)
    extent = [left, right, bottom, top]
    valid = arr[np.isfinite(arr)]
    lo = vmin if vmin is not None else (float(np.percentile(valid, 2)) if valid.size else 0)
    hi = vmax if vmax is not None else (float(np.percentile(valid, 98)) if valid.size else 1)

    fig, ax = plt.subplots(figsize=figsize, dpi=120)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    im = ax.imshow(arr, cmap=cmap, extent=extent, vmin=lo, vmax=hi, interpolation="bilinear", aspect="equal", origin="upper")

    if lgas is not None:
        lgas_plot = lgas.to_crs(profile["crs"]) if lgas.crs != profile["crs"] else lgas
        lgas_plot.boundary.plot(ax=ax, edgecolor="white", linewidth=0.7, alpha=0.65)
        if annotate_lgas:
            for _, row in lgas_plot.iterrows():
                name = str(row.get("target_lga_name", row.get("lga_name", row.get("LGA", ""))))
                if name:
                    point = row.geometry.representative_point()
                    ax.annotate(
                        name,
                        xy=(point.x, point.y),
                        ha="center",
                        va="center",
                        fontsize=6,
                    color="#111111",
                    alpha=0.9,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", alpha=0.68, lw=0),
                )

    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label(label, color="#111111", fontsize=10)
    cb.ax.yaxis.set_tick_params(color="#111111", labelsize=9)
    import matplotlib.pyplot as plt

    plt.setp(cb.ax.yaxis.get_ticklabels(), color="#111111")
    ax.set_title(title, color="#111111", fontsize=15, pad=8, fontweight="bold")
    ax.tick_params(colors="#111111", labelsize=9)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    ax.set_xlabel("Easting", color="#111111", fontsize=11)
    ax.set_ylabel("Northing", color="#111111", fontsize=11)
    fig.tight_layout(pad=0.5)
    return fig


def render_vector_map(gdf, col=None, cmap="RdYlGn_r", title="", label="", boundary=None, figsize=(9, 7)):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize, dpi=110)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    if boundary is not None:
        boundary.to_crs(gdf.crs).boundary.plot(ax=ax, edgecolor="#111111", linewidth=1.0)
    if col and col in gdf.columns:
        gdf.plot(column=col, cmap=cmap, ax=ax, legend=True, legend_kwds={"label": label, "shrink": 0.7})
    else:
        gdf.plot(ax=ax, facecolor="#444444", edgecolor="white", linewidth=0.8)
    ax.set_title(title, color="#111111", fontsize=15, fontweight="bold", pad=8)
    ax.set_axis_off()
    fig.tight_layout(pad=0.3)
    return fig


def render_interactive_lga_map(lgas, height: int = 620) -> None:
    """Render an interactive Leaflet map for the Ibadan LGA layer."""
    try:
        import folium
        from folium import plugins
    except Exception:
        st.info("Interactive map requires `folium`. Install it or use the static map pages.")
        return

    if lgas is None or lgas.empty:
        st.info("LGA boundary not available.")
        return

    gdf = lgas.to_crs("EPSG:4326").copy()
    name_col = next((c for c in ["target_lga_name", "lga_name", "LGA", "NAME_2"] if c in gdf.columns), None)
    if name_col is None:
        gdf["lga_name"] = [f"LGA {i + 1}" for i in range(len(gdf))]
        name_col = "lga_name"
    if "zone_type" not in gdf.columns:
        gdf["zone_type"] = "unclassified"

    centroid = gdf.geometry.unary_union.centroid
    fmap = folium.Map(
        location=[float(centroid.y), float(centroid.x)],
        zoom_start=10,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=True, show=True).add_to(fmap)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Esri World Imagery",
        control=True,
        show=False,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="CartoDB positron",
        name="CartoDB Positron",
        control=True,
        show=False,
    ).add_to(fmap)
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="CartoDB Dark Matter",
        control=True,
        show=False,
    ).add_to(fmap)

    color_lookup = {
        "core_urban": "#F97316",
        "peri_urban": "#38BDF8",
        "unclassified": "#94A3B8",
    }

    def style_function(feature):
        zone = feature["properties"].get("zone_type") or "unclassified"
        color = color_lookup.get(zone, color_lookup["unclassified"])
        return {
            "fillColor": color,
            "color": "#FFFFFF",
            "weight": 1.5,
            "fillOpacity": 0.45,
        }

    tooltip_fields = [name_col, "zone_type"]
    tooltip_aliases = ["LGA", "Zone"]
    folium.GeoJson(
        gdf.to_json(),
        name="Ibadan LGAs",
        style_function=style_function,
        highlight_function=lambda feature: {
            "fillOpacity": 0.72,
            "weight": 3,
            "color": "#FFFFFF",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
            sticky=True,
            labels=True,
            style=(
                "background-color: #111827; color: #FFFFFF; "
                "font-size: 15px; border: 1px solid #F97316; border-radius: 6px;"
            ),
        ),
    ).add_to(fmap)

    for _, row in gdf.iterrows():
        point = row.geometry.representative_point()
        folium.Marker(
            [float(point.y), float(point.x)],
            icon=folium.DivIcon(
                html=(
                    '<div style="font-size: 12px; font-weight: 800; color: white; '
                    'text-shadow: 0 1px 3px black; white-space: nowrap;">'
                    f"{row[name_col]}</div>"
                )
            ),
        ).add_to(fmap)

    title_html = """
    <div style="
        position: fixed;
        top: 14px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: rgba(8, 17, 31, 0.88);
        color: white;
        padding: 8px 14px;
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 6px;
        font-size: 18px;
        font-weight: 900;">
        Ibadan Metropolitan Study Area
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(title_html))
    plugins.Fullscreen(position="topright").add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    bounds = gdf.total_bounds
    fmap.fit_bounds(
        [[float(bounds[1]), float(bounds[0])], [float(bounds[3]), float(bounds[2])]]
    )
    legend_html = """
    <div style="
        position: fixed;
        bottom: 28px;
        left: 28px;
        z-index: 9999;
        background: rgba(8, 17, 31, 0.88);
        color: white;
        padding: 10px 12px;
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 6px;
        font-size: 14px;
        line-height: 1.5;">
        <b>LGA zone</b><br>
        <span style="display:inline-block;width:13px;height:13px;background:#F97316;margin-right:6px;"></span>Core urban<br>
        <span style="display:inline-block;width:13px;height:13px;background:#38BDF8;margin-right:6px;"></span>Peri-urban / fringe
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
    components.html(
        fmap.get_root().render(),
        height=height,
        scrolling=False,
    )


def no_data(filename: str, cmd: str):
    st.info(
        f"**{filename}** has not been generated yet.\n\nRun the pipeline step first:\n```\n{cmd}\n```",
        icon="ℹ️",
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">Ibadan Heat Risk<br>Engine</div>
            <div class="sidebar-subtitle">Urban heat intelligence · Ibadan Metropolis · Oyo State, Nigeria</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_project_about() -> None:
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div class="sidebar-about-title">About Project</div>
        <p>
        A reproducible geospatial intelligence dashboard for mapping LST,
        UHI hot spots, GWR heat drivers, and thermal vulnerability across
        Ibadan Metropolis.
        </p>
        <a class="github-link" href="https://github.com/Marvii/ibadan-urban-heat-risk" target="_blank">GitHub Repository</a>
        """,
        unsafe_allow_html=True,
    )


def sidebar_year() -> int:
    apply_dashboard_style()
    render_sidebar_brand()
    st.sidebar.markdown("---")
    year = st.sidebar.selectbox("Analysis year", YEARS, index=1)
    render_sidebar_project_about()
    return year


def stat_card(col, label: str, value: str, delta: str = ""):
    with col:
        st.metric(label, value, delta or None)
