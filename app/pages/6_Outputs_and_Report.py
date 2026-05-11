from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import PROJECT_ROOT, file_status_table, load_catalog, load_csv, load_text, pp, rel, sidebar_year


st.set_page_config(page_title="Outputs & Report", layout="wide")
st.title("Outputs, Reports, and Reproducibility")
st.caption("Generated files for GitHub, Streamlit Cloud, GIS desktop use, and academic reporting.")

year = sidebar_year()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "Run the output generator:\n\n"
    f"`python scripts/09_generate_outputs.py --year {year}`"
)

status = file_status_table(year)
available_count = int(status["available"].sum())
st.metric("Tracked output/source files available", f"{available_count}/{len(status)}")
st.dataframe(status, use_container_width=True, hide_index=True)

catalog = load_catalog(year)
st.markdown("---")
st.subheader("Output Catalog")
if catalog is None:
    st.info(
        "Output catalog not found. Generate it with:\n\n"
        f"`python scripts/09_generate_outputs.py --year {year}`"
    )
else:
    kind_filter = st.multiselect(
        "Filter by file type",
        sorted(catalog["kind"].dropna().unique().tolist()),
        default=sorted(catalog["kind"].dropna().unique().tolist()),
    )
    shown = catalog[catalog["kind"].isin(kind_filter)] if kind_filter else catalog
    st.dataframe(shown, use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("PDF and Markdown Reports")
pdf_path = pp("outputs/reports/ibadan_heat_risk_summary_{y}.pdf", y=year)
md_path = pp("outputs/reports/ibadan_heat_risk_summary_{y}.md", y=year)

col_pdf, col_md = st.columns(2)
with col_pdf:
    st.markdown("**PDF Report**")
    st.code(rel(pdf_path))
    if pdf_path.exists():
        st.download_button(
            "Download PDF report",
            data=pdf_path.read_bytes(),
            file_name=pdf_path.name,
            mime="application/pdf",
        )
    else:
        st.warning("PDF report has not been generated.")

with col_md:
    st.markdown("**Markdown Report**")
    st.code(rel(md_path))
    text = load_text(str(md_path))
    if text:
        with st.expander("Preview Markdown report", expanded=False):
            st.markdown(text)
    else:
        st.warning("Markdown report has not been generated.")

st.markdown("---")
st.subheader("Generated Cartographic Maps")
map_dir = PROJECT_ROOT / "outputs/maps"
maps = sorted(map_dir.glob(f"*_{year}.png")) if map_dir.exists() else []
if not maps:
    st.info(f"No PNG maps found for {year}. Run `python scripts/09_generate_outputs.py --year {year}`.")
else:
    cols = st.columns(2)
    for idx, map_path in enumerate(maps):
        with cols[idx % 2]:
            st.image(str(map_path), caption=rel(map_path), use_container_width=True)

st.markdown("---")
st.subheader("Key Tables")
table_paths = {
    "HVI ranking": pp("outputs/tables/ibadan_hvi_ranking_{y}.csv", y=year),
    "LGA LST summary": pp("outputs/tables/lga_lst_summary_{y}.csv", y=year),
    "LGA HVI summary": pp("outputs/tables/lga_hvi_summary_{y}.csv", y=year),
    "Moran's I": pp("outputs/tables/morans_i_{y}.csv", y=year),
    "GWR VIF": pp("outputs/tables/gwr_input_vif_{y}.csv", y=year),
    "GWR OLS coefficients": pp("outputs/tables/gwr_global_ols_coefficients_{y}.csv", y=year),
}
for label, path in table_paths.items():
    df = load_csv(str(path))
    with st.expander(label, expanded=False):
        st.code(rel(path))
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Table not available yet.")

st.markdown("---")
st.subheader("Streamlit Cloud Deployment Notes")
st.markdown(
    "- Keep `requirements.txt` at the repository root.\n"
    "- Main app path: `app/streamlit_app.py`.\n"
    "- Large raw rasters should generally stay out of GitHub.\n"
    "- Commit lightweight outputs such as `outputs/maps`, `outputs/tables`, `outputs/reports`, and `outputs/catalog` if the deployed app should show precomputed results.\n"
    "- If processed rasters and GeoPackages are too large for GitHub, use the generated PNG maps and CSV tables as the web-facing artifacts."
)
