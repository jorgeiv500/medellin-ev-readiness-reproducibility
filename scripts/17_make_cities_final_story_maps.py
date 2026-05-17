"""
Final Cities map system.

This script replaces repeated choropleths with three figures that each answer a
different editorial question:

1. Why Medellin's EV-charging transition is territorially constrained.
2. Which traps are dissolved, persistent, or sensitive to the expansion rule.
3. Where the candidate opportunity set and scenario selections are located.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
PROCESSED = ROOT / "data_processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

WGS84 = "EPSG:4326"
BBOX = (-75.72, 6.08, -75.40, 6.42)
PAGE = "#ffffff"
INK = "#27211f"
MUTED = "#5f6872"
BOUNDARY = "#3f4852"
INNER_EDGE = "#ffffff"

TRAP_CMAP = LinearSegmentedColormap.from_list(
    "trap", ["#f7f7f7", "#f6d6dd", "#e58ca1", "#c4415d", "#67001f"]
)
PENALTY_CMAP = LinearSegmentedColormap.from_list(
    "penalty", ["#f7fbff", "#d6e7f5", "#9ecae1", "#4292c6", "#08519c"]
)
SLOPE_CMAP = LinearSegmentedColormap.from_list(
    "slope", ["#f8f8f8", "#d9d9d9", "#969696", "#525252"]
)
MARGIN_CMAP = LinearSegmentedColormap.from_list(
    "margin", ["#f7fbff", "#d6e7f5", "#9ecae1", "#4292c6", "#08519c"]
)
DIFF_CMAP = LinearSegmentedColormap.from_list(
    "rule_difference", ["#2166ac", "#f7f7f7", "#b2182b"]
)

BIVAR_COLORS = {
    (0, 0): "#f7f7f7",
    (1, 0): "#d9e8f5",
    (2, 0): "#8db9dd",
    (0, 1): "#f4d6d6",
    (1, 1): "#c9c9c9",
    (2, 1): "#6fa3cf",
    (0, 2): "#e88989",
    (1, 2): "#b45f7a",
    (2, 2): "#542788",
}

TYPOLOGY = {
    "network access": "#0d5f63",
    "topography": "#8b5e34",
    "home charging": "#75539a",
    "vulnerability": "#b23a3a",
    "mobility pressure": "#d8842f",
}

SCENARIOS = {
    "coverage_first": ("Coverage-first", "#8a8d56"),
    "market_ready": ("Market-ready", "#6f7f4f"),
    "mobility_hub": ("Mobility-hub", "#416f9f"),
    "equity_transition": ("Equity-transition", "#c5523d"),
    "balanced_governance": ("Balanced-governance", "#6d5b8c"),
}

PERSISTENCE = {
    "not baseline trap": "#f7f7f7",
    "dissolved by all rules": "#9fc4b3",
    "rule-dependent trap": "#fdb863",
    "persistent across rules": "#67001f",
}

TYPE_COLORS = {
    "sitva_node": "#416f9f",
    "parking": "#8a8d56",
    "fuel_station": "#b65b3f",
    "centrality": "#6d5b8c",
    "public_facility": "#0d5f63",
    "commercial_or_activity_anchor": "#d8842f",
}


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.3,
            "axes.titlesize": 7.6,
            "axes.labelsize": 7.3,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "legend.fontsize": 6.6,
            "savefig.dpi": 340,
            "axes.linewidth": 0.55,
        }
    )
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)


def read_geo(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(WGS84)


def hillshade() -> tuple[np.ndarray | None, tuple[float, float, float, float] | None]:
    path = RAW / "topography" / "N06W076.hgt"
    if not path.exists():
        return None, None
    data = np.fromfile(path, dtype=">i2").reshape((3601, 3601)).astype(float)
    data[data < -1000] = np.nan
    lon0, lat_top = -76.0, 7.0
    minlon, minlat, maxlon, maxlat = BBOX
    row0 = max(0, int((lat_top - maxlat) * 3600))
    row1 = min(3601, int((lat_top - minlat) * 3600) + 1)
    col0 = max(0, int((minlon - lon0) * 3600))
    col1 = min(3601, int((maxlon - lon0) * 3600) + 1)
    z = data[row0:row1, col0:col1]
    z = np.nan_to_num(z, nan=np.nanmedian(z))
    shade = LightSource(azdeg=315, altdeg=45).hillshade(z, vert_exag=0.8, dx=1, dy=1)
    extent = (
        lon0 + col0 / 3600,
        lon0 + (col1 - 1) / 3600,
        lat_top - (row1 - 1) / 3600,
        lat_top - row0 / 3600,
    )
    return shade, extent


SHADE, SHADE_EXTENT = hillshade()


def set_map(ax) -> None:
    ax.set_facecolor(PAGE)
    ax.set_xlim(BBOX[0], BBOX[2])
    ax.set_ylim(BBOX[1], BBOX[3])
    ax.set_aspect("equal")
    ax.set_axis_off()
    if SHADE is not None and SHADE_EXTENT is not None:
        ax.imshow(SHADE, extent=SHADE_EXTENT, cmap="Greys", alpha=0.10, origin="upper", zorder=0)


def plot_boundaries(ax, zones: gpd.GeoDataFrame, lw: float = 0.22) -> None:
    zones.boundary.plot(ax=ax, color=INNER_EDGE, linewidth=lw, zorder=5)


def add_colorbar(fig, ax, cmap, norm, label: str) -> None:
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, fraction=0.035, pad=0.012)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=6.2)
    cb.set_label(label, fontsize=6.7)


def legend_bivariate(ax) -> None:
    inset = ax.inset_axes([0.045, 0.045, 0.19, 0.19])
    inset.set_facecolor(PAGE)
    for x in range(3):
        for y in range(3):
            inset.add_patch(Rectangle((x, y), 1, 1, facecolor=BIVAR_COLORS[(x, y)], edgecolor=PAGE, linewidth=0.5))
    inset.set_xlim(0, 3)
    inset.set_ylim(0, 3)
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_visible(False)
    inset.text(1.5, -0.35, "access gap", ha="center", va="top", fontsize=5.6, color=MUTED)
    inset.text(-0.28, 1.5, "pressure", ha="right", va="center", rotation=90, fontsize=5.6, color=MUTED)


def make_figure1(zones, chargers, transit, roads) -> None:
    z = zones.copy()
    z["access_gap"] = 1 - z["access_screen"].fillna(0)
    z["access_bin"] = pd.qcut(z["access_gap"].rank(method="first"), 3, labels=False)
    z["pressure_bin"] = pd.qcut(z["transition_pressure"].rank(method="first"), 3, labels=False)
    z["bivar_color"] = [BIVAR_COLORS[(int(a), int(p))] for a, p in zip(z["access_bin"], z["pressure_bin"])]

    fig, axes = plt.subplots(2, 2, figsize=(10.2, 8.2), facecolor=PAGE, constrained_layout=True)
    axes = axes.ravel()

    ax = axes[0]
    set_map(ax)
    norm = Normalize(0, 1)
    z.plot(ax=ax, column="topography_burden_screen", cmap=SLOPE_CMAP, norm=norm, linewidth=0.2, edgecolor=INNER_EDGE, alpha=0.92, zorder=2)
    if not roads.empty:
        roads.plot(ax=ax, color="#fffaf0", linewidth=0.45, alpha=0.55, zorder=4)
    if not transit.empty:
        transit.plot(ax=ax, color=INK, linewidth=1.05, alpha=0.88, zorder=6)
    if not chargers.empty:
        chargers.plot(ax=ax, color="#0d5f63", markersize=18, edgecolor=PAGE, linewidth=0.4, zorder=7)
    ax.set_title("(a) valley-ladera terrain and mobility spine", loc="left", fontweight="bold")
    add_colorbar(fig, ax, SLOPE_CMAP, norm, "topographic burden")

    ax = axes[1]
    set_map(ax)
    z.plot(ax=ax, color=z["bivar_color"], linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    plot_boundaries(ax, z)
    ax.set_title("(b) readiness-trap mechanism", loc="left", fontweight="bold")
    legend_bivariate(ax)

    ax = axes[2]
    set_map(ax)
    z.plot(ax=ax, column="topography_burden_screen", cmap=PENALTY_CMAP, norm=norm, linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    if not chargers.empty:
        chargers.plot(ax=ax, color="#30202a", markersize=14, edgecolor=PAGE, linewidth=0.35, zorder=7)
    ax.set_title("(c) topographic burden and road form", loc="left", fontweight="bold")
    add_colorbar(fig, ax, PENALTY_CMAP, norm, "topographic burden")

    ax = axes[3]
    set_map(ax)
    colors = z["binding_constraint"].map(TYPOLOGY).fillna("#c8c0b5")
    z.plot(ax=ax, color=colors, linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    ax.set_title("(d) dominant territorial bottleneck", loc="left", fontweight="bold")
    ax.legend(
        handles=[Patch(facecolor=v, label=k) for k, v in TYPOLOGY.items()],
        loc="lower right",
        frameon=True,
        framealpha=0.88,
        facecolor=PAGE,
        edgecolor="none",
    )

    out = FIGURES / "fig_cities01_feature_matrix.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    print(f"Wrote {out.relative_to(ROOT)}")


def scenario_variables(outcomes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    base = outcomes[outcomes["scenario"].eq("equity_transition")].copy()
    threshold = base["disadvantage_before"].quantile(0.75)
    piv_red = outcomes.pivot(index="zone_id", columns="scenario", values="disadvantage_reduction")
    piv_after = outcomes.pivot(index="zone_id", columns="scenario", values="disadvantage_after")
    best = piv_red.idxmax(axis=1)
    sorted_vals = np.sort(piv_red.to_numpy(dtype=float), axis=1)
    margin = sorted_vals[:, -1] - sorted_vals[:, -2]
    remaining = (piv_after >= threshold).sum(axis=1)

    base = base.set_index("zone_id")
    base["rule_margin"] = pd.Series(margin, index=piv_red.index)
    base["best_rule"] = best
    base["remaining_trap_count"] = remaining
    base["baseline_trap"] = base["disadvantage_before"] >= threshold
    base["persistence_class"] = "not baseline trap"
    base.loc[base["baseline_trap"] & (base["remaining_trap_count"] == 0), "persistence_class"] = "dissolved by all rules"
    base.loc[base["baseline_trap"] & (base["remaining_trap_count"].between(1, 4)), "persistence_class"] = "rule-dependent trap"
    base.loc[base["baseline_trap"] & (base["remaining_trap_count"] == 5), "persistence_class"] = "persistent across rules"
    base["best_rule_label"] = base["best_rule"].map({k: v[0] for k, v in SCENARIOS.items()})
    base.loc[base["rule_margin"] < 0.002, "best_rule_label"] = "no clear rule difference"
    return base.reset_index()


def make_figure2(outcomes) -> gpd.GeoDataFrame:
    story = scenario_variables(outcomes).to_crs(WGS84)
    trap = story[story["baseline_trap"]]
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 8.2), facecolor=PAGE, constrained_layout=True)
    axes = axes.ravel()

    ax = axes[0]
    set_map(ax)
    norm = Normalize(0, float(story["disadvantage_before"].quantile(0.98)))
    story.plot(ax=ax, column="disadvantage_before", cmap=TRAP_CMAP, norm=norm, linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    trap.boundary.plot(ax=ax, color=BOUNDARY, linewidth=0.52, zorder=5)
    ax.set_title("(a) baseline readiness-trap surface", loc="left", fontweight="bold")
    add_colorbar(fig, ax, TRAP_CMAP, norm, "disadvantage")

    ax = axes[1]
    set_map(ax)
    story.plot(ax=ax, color=story["persistence_class"].map(PERSISTENCE), linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    ax.set_title("(b) what remains after expansion", loc="left", fontweight="bold")
    ax.legend(
        handles=[Patch(facecolor=v, label=k) for k, v in PERSISTENCE.items()],
        loc="lower right",
        frameon=True,
        framealpha=0.88,
        facecolor=PAGE,
        edgecolor="none",
    )

    ax = axes[2]
    set_map(ax)
    margin_norm = Normalize(0, max(0.005, float(story["rule_margin"].quantile(0.98))))
    story.plot(ax=ax, column="rule_margin", cmap=MARGIN_CMAP, norm=margin_norm, linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    trap.boundary.plot(ax=ax, color=BOUNDARY, linewidth=0.38, zorder=5)
    ax.set_title("(c) where the choice of rule matters", loc="left", fontweight="bold")
    add_colorbar(fig, ax, MARGIN_CMAP, margin_norm, "best-vs-second gain")

    ax = axes[3]
    set_map(ax)
    best_colors = {"no clear rule difference": "#eeeeee"}
    best_colors.update({label: color for _, (label, color) in SCENARIOS.items()})
    story.plot(ax=ax, color=story["best_rule_label"].map(best_colors), linewidth=0.24, edgecolor=INNER_EDGE, zorder=2)
    ax.set_title("(d) best-performing rule where distinguishable", loc="left", fontweight="bold")
    ax.legend(
        handles=[Patch(facecolor=v, label=k) for k, v in best_colors.items()],
        loc="lower right",
        frameon=True,
        framealpha=0.88,
        facecolor=PAGE,
        edgecolor="none",
    )

    out = FIGURES / "fig_cities02_response_matrix.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    print(f"Wrote {out.relative_to(ROOT)}")
    return story


def make_figure3(story, selected, candidates, outcomes) -> None:
    selected = selected.to_crs(WGS84)
    outcomes = outcomes.to_crs(WGS84)
    piv = outcomes.pivot(index="zone_id", columns="scenario", values="disadvantage_reduction")
    diff = (piv.get("equity_transition", 0) - piv.get("market_ready", 0)).rename("equity_minus_market")
    story = story.set_index("zone_id").join(diff, how="left").reset_index()
    story["equity_minus_market"] = story["equity_minus_market"].fillna(0)

    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.8), facecolor=PAGE, constrained_layout=True)
    axes = axes.ravel()

    base_norm = Normalize(0, float(story["disadvantage_before"].quantile(0.98)))
    focus = [
        ("market_ready", "Market-ready rule", "parking and fuel opportunities become visible first"),
        ("equity_transition", "Equity-transition rule", "selected sites are pulled toward readiness-trap catchments"),
    ]

    for idx, (ax, (scenario, title, subtitle)) in enumerate(zip(axes[:2], focus)):
        set_map(ax)
        story.plot(ax=ax, column="disadvantage_before", cmap=TRAP_CMAP, norm=base_norm, linewidth=0.22, edgecolor=INNER_EDGE, alpha=0.82, zorder=2)
        story[story["baseline_trap"]].boundary.plot(ax=ax, color=BOUNDARY, linewidth=0.48, zorder=5)
        subset = selected[selected["scenario"].eq(scenario)]
        if not subset.empty:
            subset.plot(ax=ax, color="#24211f", markersize=15, edgecolor=PAGE, linewidth=0.42, zorder=7)
        ax.set_title(f"({chr(97 + idx)}) {title}", loc="left", fontweight="semibold")

    ax = axes[2]
    set_map(ax)
    diff_threshold = max(0.004, float(story["equity_minus_market"].abs().quantile(0.40)))
    story["diff_class"] = np.select(
        [
            story["equity_minus_market"].gt(diff_threshold),
            story["equity_minus_market"].lt(-diff_threshold),
        ],
        ["equity-transition higher", "market-ready higher"],
        default="little difference",
    )
    diff_colors = {
        "equity-transition higher": "#b2182b",
        "little difference": "#eeeeee",
        "market-ready higher": "#2166ac",
    }
    story.plot(ax=ax, color=story["diff_class"].map(diff_colors), linewidth=0.22, edgecolor=INNER_EDGE, zorder=2)
    story[story["baseline_trap"]].boundary.plot(ax=ax, color=BOUNDARY, linewidth=0.48, zorder=5)
    ax.set_title("(c) equity gain minus market gain", loc="left", fontweight="semibold")
    ax.legend(
        handles=[Patch(facecolor=v, label=k) for k, v in diff_colors.items()],
        loc="lower right",
        frameon=False,
        fontsize=6.0,
    )

    out = FIGURES / "fig_cities_readiness_trap_counterfactual.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    print(f"Wrote {out.relative_to(ROOT)}")


def update_manifest() -> None:
    rows = [
        {
            "file": "fig_cities01_feature_matrix.png",
            "role": "mechanism",
            "figure": "fig_cities01_feature_matrix.png",
            "status": "generated",
            "description": "Terrain, bivariate readiness trap, topographic burden and dominant bottleneck.",
        },
        {
            "file": "fig_cities02_response_matrix.png",
            "role": "response",
            "figure": "fig_cities02_response_matrix.png",
            "status": "generated",
            "description": "Baseline trap, persistence, rule sensitivity and best-rule geography.",
        },
        {
            "file": "fig_cities_readiness_trap_counterfactual.png",
            "role": "counterfactual",
            "figure": "fig_cities_readiness_trap_counterfactual.png",
            "status": "generated",
            "description": "Market-ready and equity-transition selected-site geographies plus equity-minus-market gain difference.",
        },
    ]
    pd.DataFrame(rows).to_csv(TABLES / "figure_manifest.csv", index=False)


def main() -> None:
    setup()
    zones = read_geo(PROCESSED / "readiness_story_screen.gpkg")
    chargers = read_geo(PROCESSED / "mapped_charger_evidence.gpkg")
    transit = read_geo(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson")
    roads = read_geo(RAW / "transport" / "geomedellin" / "road_hierarchy.geojson")
    outcomes = read_geo(PROCESSED / "counterfactual_zone_outcomes.gpkg")
    selected = read_geo(PROCESSED / "counterfactual_selected_sites.gpkg")
    candidates = read_geo(PROCESSED / "counterfactual_candidate_universe.gpkg")
    make_figure1(zones, chargers, transit, roads)
    story = make_figure2(outcomes)
    make_figure3(story, selected, candidates, outcomes)
    update_manifest()


if __name__ == "__main__":
    main()
