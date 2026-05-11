from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


def regression_summary_table(values: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame([values])


def correlation_matrix(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return data[columns].corr(numeric_only=True)


def vif_table(data: pd.DataFrame, predictors: list[str]) -> pd.DataFrame:
    """Calculate variance inflation factors for predictor screening."""
    x = data[predictors].replace([np.inf, -np.inf], np.nan).dropna()
    if x.empty:
        return pd.DataFrame(columns=["variable", "vif"])

    x_const = sm.add_constant(x, has_constant="add")
    rows = []
    for idx, column in enumerate(x_const.columns):
        if column == "const":
            continue
        rows.append(
            {
                "variable": column,
                "vif": float(variance_inflation_factor(x_const.values, idx)),
            }
        )
    return pd.DataFrame(rows).sort_values("vif", ascending=False)


def ols_diagnostics(data: pd.DataFrame, dependent: str, predictors: list[str]) -> tuple[pd.DataFrame, str]:
    """Fit global OLS and return coefficient diagnostics plus text summary."""
    model_data = data[[dependent, *predictors]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(model_data) < len(predictors) + 5:
        empty = pd.DataFrame(columns=["variable", "estimate", "std_error", "t_value", "p_value"])
        return empty, "Not enough complete observations to fit OLS diagnostics."

    y = model_data[dependent]
    x = sm.add_constant(model_data[predictors], has_constant="add")
    results = sm.OLS(y, x).fit()
    table = pd.DataFrame(
        {
            "variable": results.params.index,
            "estimate": results.params.values,
            "std_error": results.bse.values,
            "t_value": results.tvalues.values,
            "p_value": results.pvalues.values,
        }
    )
    return table, str(results.summary())


def write_model_diagnostics(
    data: pd.DataFrame,
    dependent: str,
    predictors: list[str],
    output_dir,
    year: int,
) -> dict[str, object]:
    """Write correlation, VIF, and global OLS diagnostics for GWR inputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    model_data = data[[dependent, *predictors]].replace([np.inf, -np.inf], np.nan).dropna()

    corr = correlation_matrix(model_data, [dependent, *predictors])
    vif = vif_table(model_data, predictors)
    ols_table, ols_summary = ols_diagnostics(model_data, dependent, predictors)

    corr_path = output_dir / f"gwr_input_correlations_{year}.csv"
    vif_path = output_dir / f"gwr_input_vif_{year}.csv"
    ols_table_path = output_dir / f"gwr_global_ols_coefficients_{year}.csv"
    ols_summary_path = output_dir / f"gwr_global_ols_summary_{year}.txt"

    corr.to_csv(corr_path)
    vif.to_csv(vif_path, index=False)
    ols_table.to_csv(ols_table_path, index=False)
    ols_summary_path.write_text(ols_summary, encoding="utf-8")

    return {
        "complete_observations": len(model_data),
        "correlation_path": corr_path,
        "vif_path": vif_path,
        "ols_table_path": ols_table_path,
        "ols_summary_path": ols_summary_path,
        "vif": vif,
        "ols_table": ols_table,
    }
