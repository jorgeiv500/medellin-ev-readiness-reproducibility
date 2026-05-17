from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict:
    with open(ROOT / path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs(paths: Iterable[str | Path]) -> None:
    for path in paths:
        (ROOT / path).mkdir(parents=True, exist_ok=True)


def minmax(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    lo = values.min(skipna=True)
    hi = values.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or np.isclose(lo, hi):
        return pd.Series(np.zeros(len(values)), index=series.index, dtype=float)
    return (values - lo) / (hi - lo)


def weighted_gini(values: pd.Series, weights: pd.Series | None = None) -> float:
    x = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    if weights is None:
        w = np.ones_like(x)
    else:
        w = pd.to_numeric(weights, errors="coerce").to_numpy(dtype=float)

    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]
    if len(x) == 0 or np.isclose(np.sum(w * x), 0):
        return float("nan")

    order = np.argsort(x)
    x = x[order]
    w = w[order]
    cumw = np.cumsum(w)
    cumxw = np.cumsum(x * w)
    return float(1 - 2 * np.sum(w * (cumxw - x * w / 2)) / (cumw[-1] * cumxw[-1]))


def palma_ratio(values: pd.Series, weights: pd.Series | None = None) -> float:
    df = pd.DataFrame({"value": pd.to_numeric(values, errors="coerce")})
    df["weight"] = 1.0 if weights is None else pd.to_numeric(weights, errors="coerce")
    df = df.dropna().query("weight > 0").sort_values("value")
    if df.empty:
        return float("nan")

    df["cum_weight_share"] = df["weight"].cumsum() / df["weight"].sum()
    bottom_40 = df.loc[df["cum_weight_share"] <= 0.40, "value"].sum()
    top_10 = df.loc[df["cum_weight_share"] >= 0.90, "value"].sum()
    if np.isclose(bottom_40, 0):
        return float("nan")
    return float(top_10 / bottom_40)


def missing_input(path: str | Path, message: str) -> None:
    full_path = ROOT / path
    if not full_path.exists():
        raise FileNotFoundError(f"Missing input: {full_path}\n{message}")

