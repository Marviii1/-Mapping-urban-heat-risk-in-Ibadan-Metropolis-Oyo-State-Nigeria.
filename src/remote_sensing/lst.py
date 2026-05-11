from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from src.utils.raster_utils import clip_raster_to_vector, read_band, write_raster


def _valid_summary(array: np.ndarray) -> dict[str, float]:
    valid = array[np.isfinite(array)]
    if valid.size == 0:
        return {"count": 0, "min": np.nan, "median": np.nan, "max": np.nan}
    return {
        "count": int(valid.size),
        "min": float(np.nanmin(valid)),
        "median": float(np.nanmedian(valid)),
        "max": float(np.nanmax(valid)),
    }


def detect_thermal_units(thermal: np.ndarray) -> str:
    """Infer whether ST_B10 values are raw DN, Kelvin, Celsius, or scaled reflectance-like.

    Landsat Collection 2 Level-2 ST_B10 is commonly distributed as raw DN and
    converted by ``DN * 0.00341802 + 149``. However, Earth Engine export scripts
    are easy to modify accidentally: ST_B10 may already be exported as Kelvin or
    Celsius. Applying the DN formula to already-scaled data produces all invalid
    LST values. This detector keeps the script robust for both cases.
    """
    valid = thermal[np.isfinite(thermal)]
    if valid.size == 0:
        return "empty"
    median = float(np.nanmedian(valid))
    maximum = float(np.nanmax(valid))
    minimum = float(np.nanmin(valid))

    if maximum > 1_000:
        return "raw_dn"
    if 240 <= median <= 340:
        return "kelvin"
    if -20 <= median <= 80 and -80 <= minimum <= 120:
        return "celsius"
    if 0 <= median <= 1.5:
        return "scaled_0_1"
    return "unknown"


def landsat_st_to_celsius(
    thermal_band_path: Path,
    output_path: Path,
    scale_factor: float = 0.00341802,
    add_offset: float = 149.0,
    units: str = "auto",
) -> Path:
    thermal, profile = read_band(thermal_band_path)
    detected = detect_thermal_units(thermal) if units == "auto" else units
    summary = _valid_summary(thermal)
    print(
        "Thermal input diagnostics: "
        f"units={detected}, valid_pixels={summary['count']}, "
        f"min={summary['min']:.3f}, median={summary['median']:.3f}, max={summary['max']:.3f}"
    )

    if detected == "raw_dn":
        lst_kelvin = thermal * scale_factor + add_offset
        lst_celsius = lst_kelvin - 273.15
    elif detected == "kelvin":
        lst_celsius = thermal - 273.15
    elif detected == "celsius":
        lst_celsius = thermal.copy()
    elif detected == "scaled_0_1":
        raise ValueError(
            "ST_B10 appears to be scaled to 0-1. Re-export ST_B10 as raw DN or Kelvin; "
            "0-1 scaling is valid for SR bands, not thermal LST."
        )
    elif detected == "empty":
        raise ValueError(f"Thermal raster has no valid pixels: {thermal_band_path}")
    else:
        raise ValueError(
            "Could not infer ST_B10 units. Expected raw DN (>1000), Kelvin (~240-340), "
            "or Celsius (~-20 to 80). Check the Earth Engine export."
        )

    lst_celsius[(lst_celsius < -20) | (lst_celsius > 80)] = np.nan
    output_summary = _valid_summary(lst_celsius)
    print(
        "LST output diagnostics: "
        f"valid_pixels={output_summary['count']}, "
        f"min={output_summary['min']:.3f}, median={output_summary['median']:.3f}, "
        f"max={output_summary['max']:.3f}"
    )
    if output_summary["count"] == 0:
        raise ValueError(
            "All LST pixels became invalid after conversion. This usually means ST_B10 "
            "was exported in unexpected units or contains only nodata."
        )
    return write_raster(output_path, lst_celsius, profile)


def compute_clipped_lst(
    thermal_band_path: Path,
    boundary_path: Path,
    output_path: Path,
    scale_factor: float,
    add_offset: float,
    units: str = "auto",
) -> Path:
    temporary = output_path.with_name(output_path.stem + "_unclipped.tif")
    landsat_st_to_celsius(thermal_band_path, temporary, scale_factor, add_offset, units=units)
    clipped = clip_raster_to_vector(temporary, boundary_path, output_path)
    with rasterio.open(clipped) as src:
        final = src.read(1).astype("float32")
        if src.nodata is not None:
            final[final == src.nodata] = np.nan
    final_summary = _valid_summary(final)
    print(
        "Clipped LST diagnostics: "
        f"valid_pixels={final_summary['count']}, "
        f"min={final_summary['min']:.3f}, median={final_summary['median']:.3f}, "
        f"max={final_summary['max']:.3f}"
    )
    if final_summary["count"] == 0:
        raise ValueError(
            "The clipped LST raster has no valid pixels. Check that the thermal raster "
            "overlaps the Ibadan boundary and that both files have correct CRS metadata."
        )
    temporary.unlink(missing_ok=True)
    return clipped
