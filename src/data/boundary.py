from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd

from src.utils.config import ensure_directory

LOGGER = logging.getLogger(__name__)

LGA_COLUMN_CANDIDATES = (
    "LGA", "lga", "lga_name", "LGA_NAME",
    "ADM2_NAME", "NAME_2", "admin2Name", "admin2_name", "NAME",
)

STATE_COLUMN_CANDIDATES = (
    "state", "STATE", "STATE_NAME",
    "ADM1_NAME", "NAME_1", "admin1Name", "admin1_name",
)


@dataclass(frozen=True)
class StudyAreaOutputs:
    lgas_path: Path
    boundary_path: Path
    lga_table_path: Path
    missing_lgas: list[str]
    lga_column: str
    state_column: str | None


# ---------------------------------------------------------------------------
# Name normalisation and column detection
# ---------------------------------------------------------------------------

def normalize_name(value: object) -> str:
    """Lower-case, strip punctuation/hyphens, collapse whitespace.

    'Ibadan North-East', 'Ibadan North East', 'IBADAN NORTH EAST' all map
    to the same key 'ibadan north east'.
    """
    text = "" if value is None else str(value)
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    by_exact = {c: c for c in columns}
    by_lower = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate in by_exact:
            return by_exact[candidate]
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    return None


def detect_lga_column(gdf: gpd.GeoDataFrame) -> str:
    col = find_column(gdf.columns, LGA_COLUMN_CANDIDATES)
    if col is None:
        raise ValueError(
            "Could not detect an LGA name column. Expected one of: "
            + ", ".join(LGA_COLUMN_CANDIDATES)
        )
    return col


def detect_state_column(gdf: gpd.GeoDataFrame) -> str | None:
    return find_column(gdf.columns, STATE_COLUMN_CANDIDATES)


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def filter_state_if_available(
    gdf: gpd.GeoDataFrame,
    state_column: str | None,
    state_name: str,
) -> gpd.GeoDataFrame:
    if state_column is None:
        LOGGER.warning("No state column detected. Proceeding without state filter.")
        return gdf.copy()

    state_key = normalize_name(state_name)
    filtered = gdf[gdf[state_column].map(normalize_name) == state_key].copy()
    if filtered.empty:
        LOGGER.warning(
            "State column '%s' found but no rows matched '%s'. Proceeding without state filter.",
            state_column, state_name,
        )
        return gdf.copy()
    LOGGER.info(
        "Filtered to state '%s' via column '%s' (%d LGAs).",
        state_name, state_column, len(filtered),
    )
    return filtered


def select_target_lgas(
    gdf: gpd.GeoDataFrame,
    lga_column: str,
    target_lgas: list[str],
) -> tuple[gpd.GeoDataFrame, list[str]]:
    target_lookup = {normalize_name(name): name for name in target_lgas}
    working = gdf.copy()
    working["_normalized_lga_name"] = working[lga_column].map(normalize_name)
    selected = working[working["_normalized_lga_name"].isin(target_lookup)].copy()

    found_keys = set(selected["_normalized_lga_name"])
    missing = [original for key, original in target_lookup.items() if key not in found_keys]

    selected["target_lga_name"] = selected["_normalized_lga_name"].map(target_lookup)
    selected = selected.drop(columns=["_normalized_lga_name"])
    return selected, missing


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def list_state_lgas(
    boundary_path: Path,
    state_name: str | None = None,
) -> pd.DataFrame:
    """Return all LGA names in the shapefile for a given state.

    Use this before running prepare_study_area to confirm how names are spelled
    in your specific Nigeria LGA boundary file.

    Example::

        python scripts/01_prepare_study_area.py \\
            --boundary data/raw/boundary/nigeria_lgas.shp \\
            --list-lgas

    Returns a DataFrame with columns:
        source_name     – raw shapefile value
        normalized_name – punctuation-stripped form used for matching
        state           – state column value (if detected)
    """
    gdf = gpd.read_file(boundary_path)
    lga_col = detect_lga_column(gdf)
    state_col = detect_state_column(gdf)

    records = []
    for _, row in gdf.iterrows():
        raw = str(row[lga_col])
        state_val = str(row[state_col]) if state_col else ""
        if state_name and normalize_name(state_val) != normalize_name(state_name):
            continue
        records.append({
            "source_name": raw,
            "normalized_name": normalize_name(raw),
            "state": state_val,
            "lga_column": lga_col,
            "state_column": state_col or "",
        })

    df = pd.DataFrame(records).drop_duplicates("source_name").sort_values("source_name")
    return df.reset_index(drop=True)


def _log_match_table(
    selected: gpd.GeoDataFrame,
    lga_column: str,
    missing: list[str],
) -> None:
    """Print a diagnostic table of matched / unmatched LGAs to the log."""
    LOGGER.info("─" * 64)
    LOGGER.info("  %-30s  %-30s", "Target name (config)", "Shapefile name (matched)")
    LOGGER.info("─" * 64)
    for _, row in selected.sort_values("target_lga_name").iterrows():
        target = row.get("target_lga_name", "")
        source = row[lga_column]
        marker = "✓" if target == source else "≈"
        LOGGER.info("  %s %-28s  %s", marker, target, source)
    for name in sorted(missing):
        LOGGER.warning("  ✗ %-28s  (NOT FOUND IN SHAPEFILE)", name)
    LOGGER.info("─" * 64)


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------

def prepare_study_area(
    boundary_path: Path,
    target_lgas: list[str],
    state_name: str,
    projected_crs: str,
    output_dir: Path,
    table_dir: Path,
    core_lgas: list[str] | None = None,
    periurban_lgas: list[str] | None = None,
) -> StudyAreaOutputs:
    if not boundary_path.exists():
        raise FileNotFoundError(
            f"Boundary file not found: {boundary_path}.\n"
            "Place the Nigeria LGA shapefile in data/raw/boundary/ first."
        )

    LOGGER.info("Reading boundary file: %s", boundary_path)
    gdf = gpd.read_file(boundary_path)
    if gdf.empty:
        raise ValueError(f"Boundary file contains no features: {boundary_path}")
    if gdf.crs is None:
        raise ValueError("Boundary layer has no CRS. Define it before running this script.")

    lga_column = detect_lga_column(gdf)
    state_column = detect_state_column(gdf)
    LOGGER.info("Detected LGA column  : %s", lga_column)
    LOGGER.info("Detected state column: %s", state_column or "not found")

    state_filtered = filter_state_if_available(gdf, state_column, state_name)
    selected, missing = select_target_lgas(state_filtered, lga_column, target_lgas)

    if selected.empty:
        raise ValueError(
            "No target Ibadan LGAs were found in the shapefile.\n"
            "Run with --list-lgas to see all Oyo State LGA names in your file, "
            "then update config/project_config.yml if needed."
        )

    # Diagnostic match table
    _log_match_table(selected, lga_column, missing)

    if missing:
        LOGGER.warning(
            "%d LGA(s) not matched — they will be absent from the boundary. "
            "Use --list-lgas to verify shapefile spelling.",
            len(missing),
        )

    # Reproject and compute area
    selected = selected.to_crs(projected_crs)
    selected["area_sq_km"] = selected.geometry.area / 1_000_000

    # Tag core urban vs peri-urban
    core_keys = {normalize_name(n) for n in (core_lgas or [])}
    periurban_keys = {normalize_name(n) for n in (periurban_lgas or [])}

    def _zone(row: pd.Series) -> str:
        key = normalize_name(row.get("target_lga_name", row[lga_column]))
        if core_keys and key in core_keys:
            return "core_urban"
        if periurban_keys and key in periurban_keys:
            return "peri_urban"
        return "unclassified"

    selected["zone_type"] = selected.apply(_zone, axis=1)

    # Dissolve to single metropolitan boundary
    dissolved = selected.dissolve().reset_index(drop=True)
    dissolved["name"] = "Ibadan Metropolis"
    dissolved["lga_count"] = len(selected)
    dissolved["area_sq_km"] = dissolved.geometry.area / 1_000_000
    dissolved = dissolved.set_crs(projected_crs, allow_override=True)

    # Write outputs
    output_dir = ensure_directory(output_dir)
    table_dir = ensure_directory(table_dir)
    lgas_path = output_dir / "ibadan_lgas.gpkg"
    boundary_output_path = output_dir / "ibadan_metropolitan_boundary.gpkg"
    lga_table_path = table_dir / "ibadan_lga_list.csv"

    selected.to_file(lgas_path, layer="ibadan_lgas", driver="GPKG")
    dissolved.to_file(boundary_output_path, layer="ibadan_metropolitan_boundary", driver="GPKG")

    table = pd.DataFrame({
        "lga_name": selected.get("target_lga_name", selected[lga_column]),
        "source_lga_name": selected[lga_column],
        "zone_type": selected["zone_type"],
        "area_sq_km": selected["area_sq_km"].round(3),
    }).sort_values("lga_name")
    table.to_csv(lga_table_path, index=False)

    n_core = (selected["zone_type"] == "core_urban").sum()
    n_peri = (selected["zone_type"] == "peri_urban").sum()
    LOGGER.info(
        "Study area ready: %d LGAs (%d core urban, %d peri-urban), %.1f km²",
        len(selected), n_core, n_peri, dissolved["area_sq_km"].iloc[0],
    )

    return StudyAreaOutputs(
        lgas_path=lgas_path,
        boundary_path=boundary_output_path,
        lga_table_path=lga_table_path,
        missing_lgas=missing,
        lga_column=lga_column,
        state_column=state_column,
    )
