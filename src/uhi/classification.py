"""UHI intensity classification into five thermal stress levels.

Class definitions
-----------------
1  Very Low   : UHI ≤ 0°C    — at or below rural reference temperature
2  Low        : 0 < UHI ≤ 2°C — weak urban heat effect
3  Moderate   : 2 < UHI ≤ 4°C — noticeable heat island
4  High       : 4 < UHI ≤ 6°C — strong heat island
5  Very High  : UHI > 6°C    — severe urban heat island

These thresholds suit a tropical West African city where dry-season UHI can
exceed 8°C over the dense urban core.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Class integer → human-readable label
UHI_CLASS_LABELS: dict[int, str] = {
    1: "Very Low",
    2: "Low",
    3: "Moderate",
    4: "High",
    5: "Very High",
}

# Class integer → lower bound (°C), upper bound (°C)  (None = unbounded)
UHI_CLASS_BOUNDS: dict[int, tuple[float | None, float | None]] = {
    1: (None, 0.0),
    2: (0.0,  2.0),
    3: (2.0,  4.0),
    4: (4.0,  6.0),
    5: (6.0,  None),
}

# Suggested hex colours for cartographic display
UHI_CLASS_COLOURS: dict[int, str] = {
    1: "#2166AC",   # blue  — cool
    2: "#92C5DE",   # light blue
    3: "#FEE08B",   # yellow — moderate
    4: "#F46D43",   # orange
    5: "#A50026",   # dark red — severe
}


def classify_uhi(uhi: np.ndarray) -> np.ndarray:
    """Classify UHI intensity (°C) into integer class codes 1–5.

    NaN pixels remain NaN in the output.

    Parameters
    ----------
    uhi:
        2-D float array of UHI intensity values (°C above rural reference).

    Returns
    -------
    float32 array of class codes {1, 2, 3, 4, 5} or NaN.
    """
    classes = np.full(uhi.shape, np.nan, dtype="float32")
    valid = np.isfinite(uhi)

    classes[valid & (uhi <= 0)]              = 1
    classes[valid & (uhi > 0) & (uhi <= 2)] = 2
    classes[valid & (uhi > 2) & (uhi <= 4)] = 3
    classes[valid & (uhi > 4) & (uhi <= 6)] = 4
    classes[valid & (uhi > 6)]              = 5

    return classes


def classify_uhi_with_stats(
    uhi: np.ndarray,
    pixel_area_km2: float = 0.0009,   # default: 30 m × 30 m ≈ 0.0009 km²
) -> tuple[np.ndarray, pd.DataFrame]:
    """Classify UHI intensity and return a per-class summary DataFrame.

    Parameters
    ----------
    uhi:
        2-D float array of UHI intensity values (°C).
    pixel_area_km2:
        Area of a single pixel in km².  Used to compute class areas.

    Returns
    -------
    classes:
        Float32 class array (see :func:`classify_uhi`).
    summary:
        DataFrame with columns [class_code, label, pixel_count, area_km2,
        pct_area, mean_uhi_celsius, min_uhi_celsius, max_uhi_celsius].
    """
    classes = classify_uhi(uhi)
    records = []
    for code, label in UHI_CLASS_LABELS.items():
        mask = classes == code
        n_pixels = int(mask.sum())
        if n_pixels == 0:
            records.append({
                "class_code": code,
                "label": label,
                "pixel_count": 0,
                "area_km2": 0.0,
                "pct_area": 0.0,
                "mean_uhi_celsius": np.nan,
                "min_uhi_celsius": np.nan,
                "max_uhi_celsius": np.nan,
            })
            continue
        vals = uhi[mask & np.isfinite(uhi)]
        records.append({
            "class_code": code,
            "label": label,
            "pixel_count": n_pixels,
            "area_km2": round(n_pixels * pixel_area_km2, 2),
            "pct_area": np.nan,          # filled below
            "mean_uhi_celsius": round(float(vals.mean()), 2),
            "min_uhi_celsius": round(float(vals.min()), 2),
            "max_uhi_celsius": round(float(vals.max()), 2),
        })

    df = pd.DataFrame(records)
    total_valid = df["pixel_count"].sum()
    df["pct_area"] = (df["pixel_count"] / total_valid * 100).round(1) if total_valid else 0.0
    return classes, df


def uhi_lga_summary(
    uhi: np.ndarray,
    lga_raster: np.ndarray,
    lga_codes: dict[int, str],
) -> pd.DataFrame:
    """Compute mean UHI intensity and dominant class per LGA raster zone.

    Parameters
    ----------
    uhi:
        2-D UHI intensity array aligned to *lga_raster*.
    lga_raster:
        2-D integer array where each value is an LGA code from *lga_codes*.
    lga_codes:
        Mapping from integer code → LGA name string.

    Returns
    -------
    DataFrame with columns [lga_name, mean_uhi, median_uhi, max_uhi,
    dominant_class, dominant_class_label, pct_high_very_high].
    """
    classes = classify_uhi(uhi)
    records = []
    for code, name in lga_codes.items():
        mask = (lga_raster == code) & np.isfinite(uhi)
        if not mask.any():
            continue
        vals = uhi[mask]
        cls_vals = classes[mask & np.isfinite(classes)].astype(int)
        dominant = int(np.bincount(cls_vals).argmax()) if cls_vals.size else 0
        pct_high = float(np.isin(cls_vals, [4, 5]).mean() * 100)
        records.append({
            "lga_name": name,
            "mean_uhi": round(float(vals.mean()), 2),
            "median_uhi": round(float(np.median(vals)), 2),
            "max_uhi": round(float(vals.max()), 2),
            "dominant_class": dominant,
            "dominant_class_label": UHI_CLASS_LABELS.get(dominant, ""),
            "pct_high_very_high": round(pct_high, 1),
        })

    return pd.DataFrame(records).sort_values("mean_uhi", ascending=False).reset_index(drop=True)
