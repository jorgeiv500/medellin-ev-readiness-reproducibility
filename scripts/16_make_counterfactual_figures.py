"""
Rebuild the Cities counterfactual visuals with a coherent editorial identity.

No bar panels. The main counterfactual figure is a cartographic atlas of
residual disadvantage: the reader should see how each governance rule leaves a
different territorial remainder. The supporting evidence figure uses line and
trade-off plots rather than generic bars.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data_processed"
RAW = ROOT / "data_raw"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
MANIFEST = TABLES / "figure_manifest.csv"

METRIC = "EPSG:3116"

PAGE = "#ffffff"
ZONE_EDGE = "#ffffff"
OUTLINE = "#3f4852"
MUTED = "#5f6872"

TRAP_CMAP = LinearSegmentedColormap.from_list(
    "cities_trap",
    ["#f7f7f7", "#eee7e9", "#dac2c8", "#bb8795", "#7b3a51"],
)
GAIN_CMAP = LinearSegmentedColormap.from_list(
    "cities_gain",
    ["#fbfcfd", "#e5eef4", "#c7dae6", "#8fb1c9", "#5e829e"],
)
LEADS_COLOR = "#7e8c99"

SCENARIOS = [
    ("coverage_first", "Coverage-first", "#4f8583", "o"),
    ("market_ready", "Market-ready", "#60798c", "s"),
    ("mobility_hub", "Mobility-hub", "#3f7fb5", "^"),
    ("equity_transition", "Equity-transition", "#ad6f82", "D"),
    ("balanced_governance", "Balanced-governance", "#806f9f", "P"),
]


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.4,
            "axes.titlesize": 8.2,
            "axes.labelsize": 7.4,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "legend.fontsize": 6.8,
            "savefig.dpi": 320,
            "axes.linewidth": 0.55,
        }
    )


def bounds(gdf: gpd.GeoDataFrame) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = gdf.total_bounds
    dx, dy = maxx - minx, maxy - miny
    return minx - 0.03 * dx, miny - 0.03 * dy, maxx + 0.03 * dx, maxy + 0.03 * dy


def setup_map(ax, bds) -> None:
    ax.set_facecolor(PAGE)
    ax.set_xlim(bds[0], bds[2])
    ax.set_ylim(bds[1], bds[3])
    ax.set_aspect("equal")
    ax.set_axis_off()


def plot_zones(ax, layer: gpd.GeoDataFrame, column: str, norm: Normalize, cmap, high_traps=None) -> None:
    layer.plot(
        ax=ax,
        column=column,
        cmap=cmap,
        norm=norm,
        linewidth=0.22,
        edgecolor=ZONE_EDGE,
        zorder=2,
    )
    if high_traps is not None and not high_traps.empty:
        high_traps.boundary.plot(ax=ax, color=OUTLINE, linewidth=0.42, zorder=5)


def update_manifest(filename: str, role: str, description: str) -> None:
    row = {"file": filename, "role": role, "figure": filename, "status": "generated", "description": description}
    if MANIFEST.exists():
        manifest = pd.read_csv(MANIFEST)
        key_col = "figure" if "figure" in manifest.columns else "file"
        manifest = manifest[manifest[key_col] != filename]
        manifest = pd.concat([manifest, pd.DataFrame([row])], ignore_index=True)
    else:
        manifest = pd.DataFrame([row])
    manifest.to_csv(MANIFEST, index=False)


def make_counterfactual_atlas() -> None:
    zones = gpd.read_file(PROCESSED / "counterfactual_zone_outcomes.gpkg").to_crs(METRIC)
    sites = gpd.read_file(PROCESSED / "counterfactual_selected_sites.gpkg").to_crs(METRIC)
    candidates = gpd.read_file(PROCESSED / "counterfactual_candidate_universe.gpkg").to_crs(METRIC)
    metrics = pd.read_csv(TABLES / "table_counterfactual_scenarios.csv").set_index("scenario")

    baseline = zones[zones["scenario"].eq("equity_transition")].copy()
    bds = bounds(baseline)
    trap_threshold = baseline["disadvantage_before"].quantile(0.75)
    high_traps = baseline[baseline["disadvantage_before"] >= trap_threshold]
    norm = Normalize(vmin=0, vmax=float(max(baseline["disadvantage_before"].quantile(0.98), zones["disadvantage_after"].quantile(0.98))))

    fig = plt.figure(figsize=(7.45, 7.10), facecolor=PAGE)
    gs = gridspec.GridSpec(
        2,
        2,
        figure=fig,
        left=0.035,
        right=0.985,
        top=0.940,
        bottom=0.112,
        wspace=0.030,
        hspace=0.135,
    )
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]

    ax_base = axes[0]
    setup_map(ax_base, bds)
    plot_zones(ax_base, baseline, "disadvantage_before", norm, TRAP_CMAP, high_traps)
    ax_base.set_title("1. Baseline trap geography", loc="left", fontweight="bold", pad=3)

    ax_leads = axes[1]
    setup_map(ax_leads, bds)
    baseline.plot(ax=ax_leads, color="#f7f7f7", edgecolor=ZONE_EDGE, linewidth=0.20, zorder=1)
    high_traps.boundary.plot(ax=ax_leads, color=OUTLINE, linewidth=0.46, zorder=4)
    if not candidates.empty:
        candidates.plot(ax=ax_leads, marker=".", color=LEADS_COLOR, markersize=2.2, alpha=0.28, zorder=3)
    ax_leads.set_title("2. Candidate validation field", loc="left", fontweight="bold", pad=3)

    contrasts = [
        (axes[2], "market_ready", "3. Market-ready proposal", "implementation ease leads"),
        (axes[3], "equity_transition", "4. Equity-transition proposal", "trap reduction leads"),
    ]
    for ax, scenario, title, note in contrasts:
        layer = zones[zones["scenario"].eq(scenario)].copy()
        scenario_sites = sites[sites["scenario"].eq(scenario)].copy()
        color, marker = [(c, mk) for s, _, c, mk in SCENARIOS if s == scenario][0]
        setup_map(ax, bds)
        plot_zones(ax, layer, "disadvantage_after", norm, TRAP_CMAP, high_traps)
        if not scenario_sites.empty:
            scenario_sites.plot(
                ax=ax,
                marker=marker,
                color=color,
                markersize=20,
                edgecolor="#ffffff",
                linewidth=0.55,
                zorder=7,
            )
        ax.set_title(title, loc="left", fontweight="bold", pad=3)

    cax = fig.add_axes([0.160, 0.055, 0.680, 0.014])
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=TRAP_CMAP), cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=6.5, length=0)
    cb.set_label("Charging-readiness disadvantage: baseline and residual after proposal", fontsize=7.2)
    out = FIGURES / "fig_cities_readiness_trap_counterfactual.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    update_manifest(
        out.name,
        "core-counterfactual",
        "Cartographic sequence from baseline trap geography to validation leads and contrasted proposal residuals.",
    )
    print(f"Wrote {out.relative_to(ROOT)}")


def parse_epm_use() -> pd.DataFrame:
    path = RAW / "chargers" / "epm_public_charging_use_2019_2025.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    month = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    if {"mes", "a_o", "total"} <= set(df.columns):
        df["month"] = df["mes"].astype(str).str.lower().map(month)
        df["year"] = pd.to_numeric(df["a_o"], errors="coerce")
        df["value"] = pd.to_numeric(df["total"], errors="coerce")
        df = df.dropna(subset=["month", "year", "value"]).copy()
        df["date"] = pd.to_datetime(dict(year=df["year"].astype(int), month=df["month"].astype(int), day=1))
        return df.sort_values("date")
    return pd.DataFrame()


def make_evidence_tradeoff_figure() -> None:
    metrics = pd.read_csv(TABLES / "table_counterfactual_scenarios.csv")
    rob_path = TABLES / "table_cities_robustness_summary.csv"
    robustness = pd.read_csv(rob_path) if rob_path.exists() else pd.DataFrame()
    epm = parse_epm_use()

    fig = plt.figure(figsize=(10.8, 3.7), facecolor=PAGE)
    gs = gridspec.GridSpec(1, 3, figure=fig, left=0.055, right=0.985, top=0.88, bottom=0.18, wspace=0.32)
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    for ax in axes:
        ax.set_facecolor(PAGE)

    ax = axes[0]
    if not epm.empty:
        monthly = epm.groupby("date")["value"].sum().reset_index()
        y = monthly["value"].clip(lower=0)
        ax.plot(monthly["date"], y, color="#0f5f66", linewidth=1.6)
        ax.fill_between(monthly["date"], y, color="#0f5f66", alpha=0.12)
    ax.set_title("(a) EPM public-use signal", loc="left", fontweight="bold")
    ax.set_ylabel("reported monthly use")
    ax.grid(axis="y", color="#d8dde3", linewidth=0.55)

    ax = axes[1]
    colors = {scenario: color for scenario, _, color, _ in SCENARIOS}
    for _, row in metrics.iterrows():
        color = colors.get(row["scenario"], "#777777")
        ax.scatter(
            row["spatial_leakage_index"],
            row["top_quartile_mean_reduction"],
            s=90 + 190 * row["mean_selected_implementation"],
            color=color,
            edgecolor="#ffffff",
            linewidth=0.65,
            zorder=4,
        )
        ax.text(
            row["spatial_leakage_index"] + 0.001,
            row["top_quartile_mean_reduction"] + 0.0007,
            row["label"].replace("-", "\n"),
            fontsize=6.4,
            color=OUTLINE,
        )
    ax.set_title("(b) scenario trade-off plane", loc="left", fontweight="bold")
    ax.set_xlabel("benefit leakage outside traps")
    ax.set_ylabel("trap-zone gain")
    ax.grid(color="#d8dde3", linewidth=0.55)

    ax = axes[2]
    if not robustness.empty and "top10_jaccard" in robustness.columns:
        r = robustness.loc[robustness["scenario"].ne("base")].copy()
        r["label"] = r["scenario"].str.replace("_", " ", regex=False)
        r = r.sort_values("top10_jaccard")
        y = np.arange(len(r))
        ax.hlines(y, 0, r["top10_jaccard"], color="#cfd6de", linewidth=1.1)
        ax.scatter(r["top10_jaccard"], y, color="#c5523d", s=20, label="top-10 overlap", zorder=3)
        if "access_gini" in r.columns:
            ax.scatter(r["access_gini"], y, color="#0f5f66", s=20, label="access Gini", zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels(r["label"], fontsize=6.4)
        ax.set_xlim(0, 1.05)
        ax.legend(frameon=False, fontsize=6.3, loc="lower right")
    ax.set_title("(c) robustness as overlap, not proof", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#d8dde3", linewidth=0.55)

    for ax in axes:
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color("#b8c0ca")
        ax.spines["bottom"].set_color("#b8c0ca")

    fig.text(
        0.055,
        0.965,
        "Operational evidence and scenario diagnostics",
        ha="left",
        va="top",
        fontsize=10.2,
        fontweight="bold",
        color=OUTLINE,
    )
    fig.text(
        0.055,
        0.925,
        "Use disclosure confirms activity; trade-off and robustness panels show why the result is a planning screen rather than a demand model.",
        ha="left",
        va="top",
        fontsize=7.1,
        color=MUTED,
    )

    out = FIGURES / "fig_cities03_evidence_robustness.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    update_manifest(
        out.name,
        "evidence-robustness",
        "Line, trade-off and dot-overlap figure replacing generic bars.",
    )
    print(f"Wrote {out.relative_to(ROOT)}")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    style()
    make_counterfactual_atlas()
    make_evidence_tradeoff_figure()


if __name__ == "__main__":
    main()
