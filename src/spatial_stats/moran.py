from __future__ import annotations

import geopandas as gpd
from esda.moran import Moran
from libpysal.weights import Queen


def global_moran(gdf: gpd.GeoDataFrame, value_column: str) -> dict[str, float]:
    weights = Queen.from_dataframe(gdf, use_index=False)
    weights.transform = "r"
    moran = Moran(gdf[value_column].values, weights)
    return {"moran_i": moran.I, "p_sim": moran.p_sim, "z_sim": moran.z_sim}
