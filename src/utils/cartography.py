from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.backends.backend_pdf import PdfPages
from rasterio.plot import plotting_extent


def raster_stats(path: Path) -> dict[str, float]:
    with rasterio.open(path) as src:
        array = src.read(1).astype("float32")
        if src.nodata is not None:
            array[array == src.nodata] = np.nan
    valid = array[np.isfinite(array)]
    if valid.size == 0:
        return {"min": np.nan, "mean": np.nan, "max": np.nan, "std": np.nan}
    return {
        "min": float(np.nanmin(valid)),
        "mean": float(np.nanmean(valid)),
        "max": float(np.nanmax(valid)),
        "std": float(np.nanstd(valid)),
    }


def _add_north_arrow(ax) -> None:
    ax.annotate(
        "N",
        xy=(0.94, 0.91),
        xytext=(0.94, 0.78),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        arrowprops=dict(facecolor="black", edgecolor="black", width=3, headwidth=12),
    )


def _add_scale_bar(ax, crs=None, length_km: float = 10) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    if crs is not None and getattr(crs, "is_geographic", False):
        mid_lat = (y0 + y1) / 2
        metres_per_degree_lon = max(1.0, 111_320 * np.cos(np.deg2rad(mid_lat)))
        length = (length_km * 1000) / metres_per_degree_lon
    else:
        length = length_km * 1000
    x_start = x0 + (x1 - x0) * 0.07
    y_start = y0 + (y1 - y0) * 0.07
    ax.plot([x_start, x_start + length], [y_start, y_start], color="black", linewidth=3)
    ax.plot([x_start, x_start], [y_start - length * 0.08, y_start + length * 0.08], color="black", linewidth=2)
    ax.plot(
        [x_start + length, x_start + length],
        [y_start - length * 0.08, y_start + length * 0.08],
        color="black",
        linewidth=2,
    )
    ax.text(
        x_start + length / 2,
        y_start + (y1 - y0) * 0.015,
        f"{length_km:g} km",
        ha="center",
        va="bottom",
        fontsize=8,
        color="black",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1.5),
    )


def _overlay_boundary(ax, boundary_path: Path, raster_crs) -> None:
    if not boundary_path.exists():
        return
    boundary = gpd.read_file(boundary_path).to_crs(raster_crs)
    boundary.boundary.plot(ax=ax, color="black", linewidth=0.8)


def save_continuous_raster_map(
    raster_path: Path,
    output_path: Path,
    title: str,
    legend_label: str,
    cmap: str,
    boundary_path: Path,
    subtitle: str = "Ibadan Metropolis, Oyo State, Nigeria",
    percentile_clip: tuple[int, int] = (2, 98),
    vmin: float | None = None,
    vmax: float | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(raster_path) as src:
        array = src.read(1).astype("float32")
        if src.nodata is not None:
            array[array == src.nodata] = np.nan
        extent = plotting_extent(src)
        valid = array[np.isfinite(array)]
        if vmin is None or vmax is None:
            calc_vmin, calc_vmax = np.nanpercentile(valid, percentile_clip) if valid.size else (0, 1)
            vmin = calc_vmin if vmin is None else vmin
            vmax = calc_vmax if vmax is None else vmax

        fig, ax = plt.subplots(figsize=(9, 8), dpi=220)
        im = ax.imshow(array, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, origin="upper")
        _overlay_boundary(ax, boundary_path, src.crs)
        _add_north_arrow(ax)
        _add_scale_bar(ax, src.crs)
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label(legend_label, fontsize=9)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        ax.text(0.5, 1.01, subtitle, transform=ax.transAxes, ha="center", va="bottom", fontsize=9)
        ax.set_xlabel("Easting")
        ax.set_ylabel("Northing")
        ax.grid(alpha=0.2, linewidth=0.4)
        fig.text(
            0.01,
            0.01,
            f"Source: Ibadan Heat Risk pipeline | Raster: {raster_path.name}",
            fontsize=7,
            color="#444444",
        )
        fig.tight_layout()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
    return output_path


def save_class_raster_map(
    raster_path: Path,
    output_path: Path,
    title: str,
    classes: dict[int, tuple[str, str]],
    boundary_path: Path,
    subtitle: str = "Ibadan Metropolis, Oyo State, Nigeria",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    codes = sorted(classes)
    colors = [classes[code][1] for code in codes]
    cmap = mcolors.ListedColormap(colors)
    norm = mcolors.BoundaryNorm([code - 0.5 for code in codes] + [codes[-1] + 0.5], cmap.N)

    with rasterio.open(raster_path) as src:
        array = src.read(1).astype("float32")
        if src.nodata is not None:
            array[array == src.nodata] = np.nan
        extent = plotting_extent(src)
        fig, ax = plt.subplots(figsize=(9, 8), dpi=220)
        ax.imshow(array, extent=extent, cmap=cmap, norm=norm, origin="upper", interpolation="nearest")
        _overlay_boundary(ax, boundary_path, src.crs)
        _add_north_arrow(ax)
        _add_scale_bar(ax, src.crs)
        handles = [mpatches.Patch(color=classes[code][1], label=f"{code}: {classes[code][0]}") for code in codes]
        ax.legend(handles=handles, title="Class", loc="lower right", framealpha=0.9, fontsize=8)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        ax.text(0.5, 1.01, subtitle, transform=ax.transAxes, ha="center", va="bottom", fontsize=9)
        ax.set_xlabel("Easting")
        ax.set_ylabel("Northing")
        ax.grid(alpha=0.2, linewidth=0.4)
        fig.text(
            0.01,
            0.01,
            f"Source: Ibadan Heat Risk pipeline | Raster: {raster_path.name}",
            fontsize=7,
            color="#444444",
        )
        fig.tight_layout()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
    return output_path


def save_vector_category_map(
    vector_path: Path,
    output_path: Path,
    title: str,
    category_column: str,
    color_map: dict[str, str],
    boundary_path: Path | None = None,
    subtitle: str = "Ibadan Metropolis, Oyo State, Nigeria",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf = gpd.read_file(vector_path)
    fig, ax = plt.subplots(figsize=(9, 8), dpi=220)
    for category, color in color_map.items():
        subset = gdf[gdf[category_column].astype(str).str.lower() == category.lower()]
        if not subset.empty:
            subset.plot(ax=ax, facecolor=color, edgecolor="none", alpha=0.85)
    if boundary_path and boundary_path.exists():
        gpd.read_file(boundary_path).to_crs(gdf.crs).boundary.plot(ax=ax, color="black", linewidth=0.7)
    _add_north_arrow(ax)
    _add_scale_bar(ax, gdf.crs)
    handles = [mpatches.Patch(color=color, label=category) for category, color in color_map.items()]
    ax.legend(handles=handles, title="Category", loc="lower right", framealpha=0.9, fontsize=8)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.text(0.5, 1.01, subtitle, transform=ax.transAxes, ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("Easting")
    ax.set_ylabel("Northing")
    ax.grid(alpha=0.2, linewidth=0.4)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def write_pdf_report(
    output_path: Path,
    year: int,
    stats: dict[str, dict[str, float]],
    tables: dict[str, Path],
    maps: dict[str, Path],
    methodology_notes: list[str],
    interpretation_notes: list[str],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(output_path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor("white")
        fig.text(0.08, 0.92, "Ibadan Urban Heat Risk Intelligence System", fontsize=18, fontweight="bold")
        fig.text(0.08, 0.885, f"Summary Report | {year}", fontsize=14)
        fig.text(
            0.08,
            0.845,
            "Urban Heat Island intensity mapping, spatial autocorrelation, GWR heat-driver modelling, "
            "and thermal vulnerability assessment for Ibadan Metropolis, Oyo State, Nigeria.",
            fontsize=9,
            wrap=True,
        )
        y = 0.79
        fig.text(0.08, y, "Methodology Conceptualisation", fontsize=13, fontweight="bold")
        y -= 0.03
        for note in methodology_notes:
            fig.text(0.1, y, f"- {note}", fontsize=9, wrap=True)
            y -= 0.026
        y -= 0.02
        fig.text(0.08, y, "Key Raster Statistics", fontsize=13, fontweight="bold")
        y -= 0.035
        for layer, values in stats.items():
            fig.text(
                0.1,
                y,
                f"{layer}: min={values.get('min', np.nan):.3f}, mean={values.get('mean', np.nan):.3f}, "
                f"max={values.get('max', np.nan):.3f}, std={values.get('std', np.nan):.3f}",
                fontsize=9,
            )
            y -= 0.025
        y -= 0.02
        fig.text(0.08, y, "Result Interpretation", fontsize=13, fontweight="bold")
        y -= 0.03
        for note in interpretation_notes:
            fig.text(0.1, y, f"- {note}", fontsize=9, wrap=True)
            y -= 0.026
        y -= 0.02
        fig.text(0.08, y, "Referenced Output Tables", fontsize=13, fontweight="bold")
        y -= 0.03
        for label, path in tables.items():
            fig.text(0.1, y, f"- {label}: {path.as_posix()}", fontsize=8)
            y -= 0.022
        fig.text(0.08, 0.04, "Generated by scripts/09_generate_outputs.py", fontsize=8, color="#444444")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        for label, map_path in maps.items():
            if not map_path.exists():
                continue
            image = plt.imread(map_path)
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.imshow(image)
            ax.set_title(label.replace("_", " ").title(), fontsize=14, fontweight="bold")
            ax.set_axis_off()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    return output_path
