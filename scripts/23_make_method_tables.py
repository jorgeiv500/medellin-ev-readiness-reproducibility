"""
Method traceability and weight-sensitivity tables for the Cities manuscript.

These tables respond to the main editorial risk: the readiness baseline must be
auditable rather than a black-box index. They are intentionally compact enough
for the manuscript/supplement and derive sensitivity results from the processed
zone screen.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data_processed"
TABLES = ROOT / "outputs" / "tables"


def minmax(values: pd.Series | np.ndarray) -> pd.Series:
    s = pd.Series(values, dtype=float)
    lo, hi = s.min(skipna=True), s.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or np.isclose(lo, hi):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def gini(values: pd.Series | np.ndarray) -> float:
    x = pd.to_numeric(pd.Series(values), errors="coerce").dropna().to_numpy(dtype=float)
    if len(x) == 0 or np.isclose(x.sum(), 0):
        return float("nan")
    x = np.sort(x)
    n = len(x)
    return float((2 * np.arange(1, n + 1) @ x) / (n * x.sum()) - (n + 1) / n)


def jaccard_top(base: pd.Series, variant: pd.Series, n: int = 10) -> float:
    base_ids = set(base.sort_values(ascending=False).head(n).index)
    variant_ids = set(variant.sort_values(ascending=False).head(n).index)
    if not base_ids and not variant_ids:
        return float("nan")
    return len(base_ids & variant_ids) / len(base_ids | variant_ids)


def latex_escape(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    for old, new in {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }.items():
        text = text.replace(old, new)
    return text


def fmt(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "--"
    return f"{value:.{digits}f}"


def write_latex_table(path: Path, header: list[str], rows: list[list[str]], align: str) -> None:
    lines = [r"\begin{tabular}{" + align + "}", r"\toprule"]
    lines.append(" & ".join(header) + r" \\")
    lines.append(r"\midrule")
    for row in rows:
        lines.append(" & ".join(row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {path.relative_to(ROOT)}")


def make_traceability_table() -> None:
    rows = [
        [
            r"$A_i$ public charging access",
            "CargaME, EPM, OSM, OSMnx drive network, SITVA/GTFS and centralities",
            "OD/SIT zone",
            "Source-weighted exponential decay using 12-minute network travel time and activity anchoring",
            "Baseline access term",
            "Decay, source-strength and activity-anchor checks",
        ],
        [
            r"$M_i$ mobility pressure",
            "AMVA EOD household/trip evidence aggregated by municipality",
            "OD/SIT zone via municipality",
            "Min--max normalized private motorized exposure",
            "Transition-pressure component, weight 0.40",
            "Weight sensitivity and no-vulnerability/no-topography checks",
        ],
        [
            r"$H_i$ home-charging constraint",
            "EOD household/parking proxy by municipality",
            "OD/SIT zone via municipality",
            "Min--max normalized residential charging constraint",
            "Transition-pressure component, weight 0.25",
            "No-home-constraint and home-heavy checks",
        ],
        [
            r"$V_i$ social vulnerability",
            "Medellin ECV poverty indicators joined to OD/SIT representative points",
            "OD/SIT zone",
            "Min--max normalized poverty screen",
            "Transition-pressure component, weight 0.25; not reused as a multiplier",
            "No-vulnerability and vulnerability-heavy checks",
        ],
        [
            r"$T_i$ topographic burden",
            "SRTM elevation and slope over OD/SIT zones",
            "OD/SIT zone",
            "Min--max normalized slope/elevation burden",
            "Transition-pressure component, weight 0.10",
            "No-topography and topography-heavy checks",
        ],
        [
            r"$D_i$ readiness trap",
            "Constructed from transition pressure and public-charging access",
            "OD/SIT zone",
            r"$D_i=N_i(1-\widetilde{A}_i)$, normalized within the study area",
            "Baseline comparison surface",
            "Weight sensitivity, access ablations and scenario residual comparison",
        ],
    ]
    pd.DataFrame(
        rows,
        columns=["indicator", "source", "unit", "transformation", "role", "sensitivity"],
    ).to_csv(TABLES / "table_cities_indicator_traceability.csv", index=False)
    write_latex_table(
        TABLES / "table_cities_indicator_traceability.tex",
        ["Indicator", "Source", "Unit", "Transformation", "Role", "Sensitivity"],
        rows,
        r"p{0.12\textwidth}p{0.18\textwidth}p{0.09\textwidth}p{0.22\textwidth}p{0.16\textwidth}p{0.14\textwidth}",
    )


def make_weight_sensitivity_table() -> None:
    zones_path = PROCESSED / "readiness_story_screen.gpkg"
    if not zones_path.exists():
        raise FileNotFoundError("Run scripts/13_make_cities_storyline_figures.py first")
    z = gpd.read_file(zones_path)
    comps = {
        "M": z["mobility_pressure"].fillna(0),
        "H": z["home_constraint_screen"].fillna(0),
        "V": z["vulnerability_screen"].fillna(0),
        "T": z["topography_burden_screen"].fillna(0),
    }
    access = z["access_screen"].fillna(0)
    base = z["disadvantage_screen"].fillna(0)
    specs = [
        ("Base", 0.40, 0.25, 0.25, 0.10, "Manuscript transition-pressure screen"),
        ("Equal weights", 0.25, 0.25, 0.25, 0.25, "No component receives priority"),
        ("Mobility-heavy", 0.50, 0.20, 0.20, 0.10, "Private motorized exposure emphasized"),
        ("Home-heavy", 0.30, 0.40, 0.20, 0.10, "Residential charging constraint emphasized"),
        ("Vulnerability-heavy", 0.30, 0.20, 0.40, 0.10, "Social vulnerability emphasized once"),
        ("Topography-heavy", 0.30, 0.20, 0.20, 0.30, "Slope/elevation burden emphasized"),
        ("No vulnerability", 0.55, 0.30, 0.00, 0.15, "Social vulnerability removed"),
        ("No topography", 0.45, 0.25, 0.30, 0.00, "Slope/elevation burden removed"),
    ]
    rows = []
    for name, wm, wh, wv, wt, reading in specs:
        transition = minmax(wm * comps["M"] + wh * comps["H"] + wv * comps["V"] + wt * comps["T"]).fillna(0)
        disadv = minmax(transition * (1 - access)).fillna(0)
        rows.append(
            {
                "specification": name,
                "M": wm,
                "H": wh,
                "V": wv,
                "T": wt,
                "disadvantage_gini": gini(disadv),
                "top10_jaccard": jaccard_top(base, disadv, 10),
                "reading": reading,
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "table_cities_weight_sensitivity.csv", index=False)
    rows_tex = [
        [
            latex_escape(row["specification"]),
            fmt(row["M"]),
            fmt(row["H"]),
            fmt(row["V"]),
            fmt(row["T"]),
            fmt(row["disadvantage_gini"]),
            fmt(row["top10_jaccard"]),
            latex_escape(row["reading"]),
        ]
        for _, row in table.iterrows()
    ]
    write_latex_table(
        TABLES / "table_cities_weight_sensitivity.tex",
        ["Specification", "$M_i$", "$H_i$", "$V_i$", "$T_i$", "Disadv. Gini", "Top-10 overlap", "Reading"],
        rows_tex,
        r"lrrrrrrp{0.30\textwidth}",
    )


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    make_traceability_table()
    make_weight_sensitivity_table()


if __name__ == "__main__":
    main()
