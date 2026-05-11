from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import rasterio
from rasterio.plot import show


def save_raster_map(raster_path: str | Path, output_path: str | Path, title: str, cmap: str = "inferno") -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(raster_path) as src:
        fig, ax = plt.subplots(figsize=(8, 8))
        show(src, ax=ax, cmap=cmap)
        ax.set_title(title)
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(output, dpi=200)
        plt.close(fig)
    return output
