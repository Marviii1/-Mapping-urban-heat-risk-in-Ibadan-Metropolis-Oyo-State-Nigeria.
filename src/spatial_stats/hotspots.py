from __future__ import annotations

import geopandas as gpd
import numpy as np
from esda.getisord import G_Local
from libpysal.weights import Queen


def getis_ord_gistar(gdf: gpd.GeoDataFrame, value_column: str) -> gpd.GeoDataFrame:
    result = gdf.copy()
    weights = Queen.from_dataframe(result, use_index=False)
    weights.transform = "r"
    gi = G_Local(result[value_column].values, weights, star=True)
    result["gi_z"] = gi.Zs
    result["gi_p"] = gi.p_sim
    label = np.array(["Not significant"] * len(result), dtype=object)
    label[(result["gi_z"] >= 1.96) & (result["gi_p"] <= 0.05)] = "Hot spot"
    label[(result["gi_z"] <= -1.96) & (result["gi_p"] <= 0.05)] = "Cold spot"
    result["gistar_cluster"] = label
    return result
