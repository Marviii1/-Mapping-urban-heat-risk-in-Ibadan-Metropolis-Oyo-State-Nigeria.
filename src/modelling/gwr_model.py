from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from mgwr.gwr import GWR
from mgwr.sel_bw import Sel_BW
from sklearn.preprocessing import StandardScaler


def _safe_attr(obj, name: str, default: object = "NA") -> object:
    return getattr(obj, name, default)


def _parameter_summary(results, predictors: list[str]) -> pd.DataFrame:
    names = ["intercept", *predictors]
    rows = []
    for idx, name in enumerate(names):
        values = results.params[:, idx]
        rows.append(
            {
                "variable": name,
                "mean": float(np.nanmean(values)),
                "std": float(np.nanstd(values)),
                "min": float(np.nanmin(values)),
                "median": float(np.nanmedian(values)),
                "max": float(np.nanmax(values)),
            }
        )
    return pd.DataFrame(rows)


def _build_summary_text(
    results,
    dependent: str,
    predictors: list[str],
    bandwidth: int,
    observations: int,
) -> str:
    parameter_table = _parameter_summary(results, predictors)
    lines = [
        "GWR model summary",
        "=================",
        f"Dependent variable: {dependent}",
        f"Predictors: {', '.join(predictors)}",
        f"Adaptive bandwidth: {bandwidth}",
        f"Complete observations: {observations}",
        "",
        "Model diagnostics",
        "=================",
        f"Residual sum of squares: {_safe_attr(results, 'RSS')}",
        f"Effective number of parameters (trace(S)): {_safe_attr(results, 'tr_S')}",
        f"Sigma estimate: {_safe_attr(results, 'sigma2')}",
        f"Log-likelihood: {_safe_attr(results, 'llf')}",
        f"AIC: {_safe_attr(results, 'aic')}",
        f"AICc: {_safe_attr(results, 'aicc')}",
        f"BIC: {_safe_attr(results, 'bic')}",
        f"R2: {_safe_attr(results, 'R2')}",
        f"Adjusted R2: {_safe_attr(results, 'adj_R2')}",
        "",
        "Coefficient field mapping",
        "=========================",
        "gwr_intercept = local intercept",
        *[f"coef_{name} = local coefficient for {name}" for name in predictors],
        "local_r2 = local coefficient of determination",
        "gwr_residual = local model residual",
        "",
        "Summary statistics for local parameter estimates",
        "===============================================",
        parameter_table.to_string(index=False),
        "",
    ]
    return "\n".join(str(line) for line in lines)


def run_gwr(
    gdf: gpd.GeoDataFrame,
    dependent: str,
    predictors: list[str],
    output_path: Path,
    summary_path: Path,
    bandwidth: int | None = None,
) -> tuple[Path, Path, str]:
    model_data = gdf.dropna(subset=[dependent, *predictors]).copy()
    if len(model_data) < len(predictors) + 5:
        raise ValueError("Not enough complete observations to fit GWR.")

    centroids = model_data.geometry.centroid
    coords = np.column_stack([centroids.x.values, centroids.y.values])
    y = model_data[[dependent]].values
    x = model_data[predictors].values
    x = StandardScaler().fit_transform(x)

    selected_bandwidth = bandwidth or int(Sel_BW(coords, y, x).search())
    results = GWR(coords, y, x, selected_bandwidth).fit()

    model_data["gwr_intercept"] = results.params[:, 0]
    for idx, predictor in enumerate(predictors, start=1):
        model_data[f"coef_{predictor}"] = results.params[:, idx]
    model_data["local_r2"] = results.localR2
    model_data["gwr_residual"] = results.resid_response.flatten()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model_data.to_file(output_path, layer="gwr_results", driver="GPKG")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_text = _build_summary_text(
        results,
        dependent=dependent,
        predictors=predictors,
        bandwidth=selected_bandwidth,
        observations=len(model_data),
    )
    summary_path.write_text(summary_text, encoding="utf-8")
    return output_path, summary_path, summary_text
