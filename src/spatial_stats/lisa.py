from __future__ import annotations

import geopandas as gpd
import numpy as np
from esda.moran import Moran_Local
from libpysal.weights import Queen


def local_moran_clusters(gdf: gpd.GeoDataFrame, value_column: str) -> gpd.GeoDataFrame:
    result = gdf.copy()
    weights = Queen.from_dataframe(result, use_index=False)
    weights.transform = "r"
    lisa = Moran_Local(result[value_column].values, weights)
    result["lisa_i"] = lisa.Is
    result["lisa_p"] = lisa.p_sim
    result["lisa_quadrant"] = lisa.q
    labels = np.array(["Not significant"] * len(result), dtype=object)
    significant = lisa.p_sim <= 0.05
    labels[(lisa.q == 1) & significant] = "High-High"
    labels[(lisa.q == 2) & significant] = "Low-High"
    labels[(lisa.q == 3) & significant] = "Low-Low"
    labels[(lisa.q == 4) & significant] = "High-Low"
    result["lisa_cluster"] = labels
    return result
