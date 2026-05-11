"""Streamlit home page for the Ibadan Urban Heat Risk dashboard."""
from __future__ import annotations

import streamlit as st

from utils import (
    BOUNDARY_PATH,
    LGAS_PATH,
    PROJECT_ROOT,
    load_csv,
    load_vector,
    pp,
    rel,
    render_interactive_lga_map,
    sidebar_year,
)


st.set_page_config(
    page_title="Ibadan Heat Risk Intelligence System",
    page_icon=":thermometer:",
    layout="wide",
    initial_sidebar_state="expanded",
)

year = sidebar_year()
st.sidebar.markdown("---")
st.sidebar.markdown(
    "Explore heat exposure, UHI hot spots, GWR heat drivers, vulnerability rankings, "
    "temporal trends, and publication-ready outputs."
)

st.title("Ibadan Urban Heat Risk Intelligence System")
st.caption(
    "Urban Heat Island intensity mapping, spatial autocorrelation analysis, "
    "GWR heat-driver modelling, and thermal vulnerability assessment for "
    "Ibadan Metropolis, Oyo State, Nigeria."
)

lgas = load_vector(str(LGAS_PATH))
boundary = load_vector(str(BOUNDARY_PATH))

n_lgas = int(len(lgas)) if lgas is not None else 0
area_km2 = None
if boundary is not None and not boundary.empty:
    area_km2 = float(boundary.to_crs("EPSG:32631").geometry.area.sum() / 1_000_000)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Target LGAs", f"{n_lgas or 11}")
col2.metric("Study Area", f"{area_km2:,.0f} km²" if area_km2 else "Ibadan Metro")
col3.metric("Selected Year", str(year))
col4.metric("Analysis Scale", "500 m", "ESDA and GWR grid")

st.markdown("---")

st.subheader("Interactive Ibadan Metropolitan Study Area")
st.markdown(
    """
    <p class="small-note">
    Core urban LGAs are shown in orange, while peri-urban/fringe LGAs are shown in blue.
    Hover over each polygon to inspect the LGA name and zone classification.
    </p>
    """,
    unsafe_allow_html=True,
)
if lgas is None:
    st.info(
        "Study-area GeoPackage not found. Run "
        "`python scripts/01_prepare_study_area.py --boundary data/raw/boundary/nigeria_lgas.shp`."
    )
else:
    render_interactive_lga_map(lgas, height=650)

st.markdown("---")
st.subheader("Most Relevant Artifacts")

artifact_cols = st.columns(3)
artifact_cards = [
    ("Cartographic maps", pp("outputs/maps/lst_{y}.png", y=year), "Publication PNG maps with legends and map furniture."),
    ("PDF report", pp("outputs/reports/ibadan_heat_risk_summary_{y}.pdf", y=year), "Summary report for methodology, results, and interpretation."),
    ("Output catalog", pp("outputs/catalog/output_catalog_{y}.csv", y=year), "Machine-readable inventory for dashboard and GitHub review."),
]
for col, (label, path, description) in zip(artifact_cols, artifact_cards):
    with col:
        status_label = "Available" if path.exists() else "Not generated yet"
        st.markdown(
            f"""
            <div class="artifact-card">
            <h3>{label}</h3>
            <p>{description}</p>
            <p><strong>{status_label}</strong></p>
            <p><code>{rel(path)}</code></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")
with st.expander("LGA Inventory", expanded=False):
    lga_table = load_csv(str(PROJECT_ROOT / "data/processed/tables/ibadan_lga_list.csv"))
    if lga_table is None:
        st.info("LGA table not found yet.")
    else:
        st.dataframe(lga_table, use_container_width=True, hide_index=True)

st.caption(
    "Data sources and derived products: Landsat 8/9, WorldPop, GHSL, OSM, "
    "GeoPandas, Rasterio, PySAL/esda, mgwr, PyDeck, Matplotlib, and Streamlit."
)
