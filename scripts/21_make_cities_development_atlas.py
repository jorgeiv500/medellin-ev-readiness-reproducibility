"""
Map-based residual atlas for the Cities manuscript.

The figure follows the visual logic used in urban accessibility and GIS-MCDA
studies: start from a baseline geography, test rule-based interventions, and
show the territories that remain difficult to serve. The full candidate cloud is
not the argument; residual geography is.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
PROCESSED = ROOT / "data_processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

WGS84 = "EPSG:4326"
BBOX = (-75.72, 6.08, -75.40, 6.42)
PAGE = "#fbfaf6"
INK = "#263034"
MUTED = "#68736f"
EDGE = "#fffdf8"
BOUNDARY = "#425055"
TRAP_EDGE = "#303a3e"
TRANSIT = "#2f3a3e"
CURRENT = "#557f78"
CANDIDATE = "#8c938e"
MARKET = "#6f8793"
EQUITY = "#b57462"
PERSISTENT = "#5d8571"

BASELINE_CMAP = LinearSegmentedColormap.from_list(
    "baseline_trap", ["#fbfaf6", "#f1e7de", "#dec9b9", "#c99680", "#96604f"]
)
RESIDUAL_CMAP = LinearSegmentedColormap.from_list(
    "residual_trap", ["#fbfaf6", "#efe8df", "#d9c7b9", "#c1917d", "#96604f"]
)
PERSISTENT_CMAP = LinearSegmentedColormap.from_list(
    "persistent_residual", ["#fbfaf6", "#e9efe7", "#c8d9c9", "#88ae94", "#4f7768"]
)
RULE_DIFF_CMAP = LinearSegmentedColormap.from_list(
    "rule_residual_difference", [EQUITY, "#fbfaf6", MARKET]
)


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 6.5,
            "axes.titlesize": 7.2,
            "legend.fontsize": 6.1,
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


def clip(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    minx, miny, maxx, maxy = BBOX
    return gdf.cx[minx:maxx, miny:maxy].copy()


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
    shade = LightSource(azdeg=315, altdeg=45).hillshade(z, vert_exag=0.75, dx=1, dy=1)
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
        ax.imshow(SHADE, extent=SHADE_EXTENT, cmap="Greys", alpha=0.055, origin="upper", zorder=0)


def add_scale(ax, cmap, norm, label: str, ticks=None, ticklabels=None) -> None:
    fig = ax.figure
    pos = ax.get_position()
    cax = fig.add_axes(
        [
            pos.x0 + pos.width * 0.18,
            pos.y0 - 0.032,
            pos.width * 0.64,
            0.011,
        ]
    )
    cax.set_facecolor(PAGE)
    cb = plt.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=5.2, length=0, pad=1)
    if ticks is not None:
        cb.set_ticks(ticks)
    if ticklabels is not None:
        cb.set_ticklabels(ticklabels)
    cb.set_label(label, fontsize=5.5, color=MUTED, labelpad=1)


def plot_base(ax, zones, transit, trap_zones) -> None:
    zones.plot(ax=ax, color="#f3f2ec", edgecolor=EDGE, linewidth=0.16, zorder=1)
    if not transit.empty:
        transit.plot(ax=ax, color=TRANSIT, linewidth=0.85, alpha=0.82, zorder=4)
    if not trap_zones.empty:
        trap_zones.boundary.plot(ax=ax, color=TRAP_EDGE, linewidth=0.48, alpha=0.88, zorder=5)


def plot_selected(ax, selected, scenario: str, color: str, marker: str) -> None:
    subset = selected[selected["scenario"].eq(scenario)]
    if subset.empty:
        return
    subset.plot(
        ax=ax,
        marker=marker,
        color=color,
        markersize=26,
        edgecolor=PAGE,
        linewidth=0.55,
        alpha=0.98,
        zorder=8,
    )


def update_manifest(filename: str) -> None:
    row = pd.DataFrame(
        [
            {
                "file": filename,
                "role": "development-atlas",
                "figure": filename,
                "status": "generated",
                "description": "Map sequence from inherited readiness baseline to residual persistence, contrasted validation leads, and rule-difference geography.",
            }
        ]
    )
    path = TABLES / "figure_manifest.csv"
    if path.exists():
        manifest = pd.read_csv(path)
        key = "figure" if "figure" in manifest.columns else "file"
        manifest = manifest[manifest[key] != filename]
        manifest = pd.concat([manifest, row], ignore_index=True)
    else:
        manifest = row
    manifest.to_csv(path, index=False)


def make_figure() -> None:
    setup()
    outcomes = clip(read_geo(PROCESSED / "counterfactual_zone_outcomes.gpkg"))
    selected = clip(read_geo(PROCESSED / "counterfactual_selected_sites.gpkg"))
    chargers = clip(read_geo(PROCESSED / "mapped_charger_evidence.gpkg"))
    transit = clip(read_geo(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson"))

    baseline = outcomes[outcomes["scenario"].eq("equity_transition")].copy()
    trap_threshold = baseline["disadvantage_before"].quantile(0.75)
    trap_zones = baseline[baseline["disadvantage_before"] >= trap_threshold].copy()
    base_norm = Normalize(0, float(baseline["disadvantage_before"].quantile(0.98)))

    # The after-expansion distribution is zero-inflated: most zones are fully
    # relieved under each rule, so an unconditional upper-quartile threshold can
    # collapse to zero and falsely classify the whole map as residual. Residual
    # persistence is therefore counted only when a zone keeps a positive score.
    residual_cut = outcomes["disadvantage_after"] > 1e-9
    persistent = (
        outcomes.assign(positive_residual=residual_cut)
        .groupby("zone_id", as_index=False)["positive_residual"]
        .sum()
        .rename(columns={"positive_residual": "persistent_residual_count"})
    )
    persistent_map = baseline.merge(persistent, on="zone_id", how="left")
    persistent_map["persistent_residual_count"] = persistent_map["persistent_residual_count"].fillna(0)
    persistent_map["baseline_trap"] = persistent_map["disadvantage_before"] >= trap_threshold
    persistent_map["trap_residual_count"] = np.where(
        persistent_map["baseline_trap"],
        persistent_map["persistent_residual_count"],
        np.nan,
    )
    persistent_norm = Normalize(0, 5)

    market = outcomes[outcomes["scenario"].eq("market_ready")].copy()
    equity = outcomes[outcomes["scenario"].eq("equity_transition")].copy()
    contrast = market[["zone_id", "disadvantage_after", "geometry"]].rename(
        columns={"disadvantage_after": "market_after"}
    )
    contrast = contrast.merge(
        equity[["zone_id", "disadvantage_after"]].rename(columns={"disadvantage_after": "equity_after"}),
        on="zone_id",
        how="left",
    )
    contrast = gpd.GeoDataFrame(contrast, geometry="geometry", crs=market.crs)
    contrast["rule_residual_difference"] = contrast["equity_after"] - contrast["market_after"]
    diff_norm = TwoSlopeNorm(vmin=-0.04, vcenter=0.0, vmax=0.01)

    fig, axes = plt.subplots(2, 2, figsize=(7.15, 7.00), facecolor=PAGE)
    fig.subplots_adjust(left=0.038, right=0.976, top=0.970, bottom=0.108, wspace=0.010, hspace=0.215)
    ax_base, ax_persistent, ax_leads, ax_contrast = axes.ravel()

    set_map(ax_base)
    baseline.plot(
        ax=ax_base,
        column="disadvantage_before",
        cmap=BASELINE_CMAP,
        norm=base_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=2,
    )
    if not transit.empty:
        transit.plot(ax=ax_base, color=TRANSIT, linewidth=0.82, alpha=0.78, zorder=4)
    if not chargers.empty:
        chargers.plot(ax=ax_base, color=CURRENT, markersize=15, edgecolor=PAGE, linewidth=0.35, zorder=7)
    trap_zones.boundary.plot(ax=ax_base, color=TRAP_EDGE, linewidth=0.52, zorder=6)
    ax_base.set_title("(a) inherited baseline trap", loc="left", fontweight="semibold", color=INK, pad=2)
    add_scale(ax_base, BASELINE_CMAP, base_norm, "baseline readiness-trap score")

    set_map(ax_persistent)
    baseline.plot(ax=ax_persistent, color="#f3f2ec", edgecolor=EDGE, linewidth=0.18, zorder=1)
    persistent_map.plot(
        ax=ax_persistent,
        column="trap_residual_count",
        cmap=PERSISTENT_CMAP,
        norm=persistent_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=2,
    )
    if not transit.empty:
        transit.plot(ax=ax_persistent, color=TRANSIT, linewidth=0.82, alpha=0.66, zorder=4)
    trap_zones.boundary.plot(ax=ax_persistent, color=TRAP_EDGE, linewidth=0.50, zorder=6)
    ax_persistent.set_title("(b) residual persistence inside baseline trap", loc="left", fontweight="semibold", color=INK, pad=2)
    add_scale(
        ax_persistent,
        PERSISTENT_CMAP,
        persistent_norm,
        "rules leaving positive residual",
        ticks=[0, 1, 2, 3, 4, 5],
        ticklabels=["0", "1", "2", "3", "4", "5"],
    )

    set_map(ax_leads)
    baseline.plot(ax=ax_leads, color="#f3f2ec", edgecolor=EDGE, linewidth=0.18, zorder=1)
    if not transit.empty:
        transit.plot(ax=ax_leads, color=TRANSIT, linewidth=0.90, alpha=0.84, zorder=4)
    if not chargers.empty:
        chargers.plot(ax=ax_leads, color=CURRENT, markersize=13, edgecolor=PAGE, linewidth=0.35, zorder=6)
    trap_zones.boundary.plot(ax=ax_leads, color=TRAP_EDGE, linewidth=0.52, alpha=0.90, zorder=5)
    plot_selected(ax_leads, selected, "market_ready", MARKET, "s")
    plot_selected(ax_leads, selected, "equity_transition", EQUITY, "D")
    ax_leads.set_title("(c) contrasted validation leads", loc="left", fontweight="semibold", color=INK, pad=2)

    set_map(ax_contrast)
    contrast.plot(
        ax=ax_contrast,
        column="rule_residual_difference",
        cmap=RULE_DIFF_CMAP,
        norm=diff_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=2,
    )
    if not transit.empty:
        transit.plot(ax=ax_contrast, color=TRANSIT, linewidth=0.82, alpha=0.72, zorder=4)
    trap_zones.boundary.plot(ax=ax_contrast, color=TRAP_EDGE, linewidth=0.48, alpha=0.86, zorder=5)
    ax_contrast.set_title("(d) residual difference between rules", loc="left", fontweight="semibold", color=INK, pad=2)
    add_scale(
        ax_contrast,
        RULE_DIFF_CMAP,
        diff_norm,
        "residual difference: equity lower <- 0 -> market lower",
        ticks=[-0.04, 0, 0.01],
        ticklabels=["equity", "0", "market"],
    )

    handles = [
        Line2D([0], [0], color=TRANSIT, lw=1.1, label="SITVA/Metro"),
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor=CURRENT, markeredgecolor=PAGE, markersize=4.8, label="mapped public charging"),
        Patch(facecolor="none", edgecolor=TRAP_EDGE, linewidth=0.8, label="baseline trap quartile"),
        Line2D([0], [0], marker="s", linestyle="", markerfacecolor=MARKET, markeredgecolor=PAGE, markersize=5.0, label="market lead"),
        Line2D([0], [0], marker="D", linestyle="", markerfacecolor=EQUITY, markeredgecolor=PAGE, markersize=5.0, label="equity lead"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.515, 0.014),
        columnspacing=1.2,
        handletextpad=0.45,
        fontsize=5.8,
    )

    out = FIGURES / "fig_cities03_baseline_to_proposals.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    update_manifest(out.name)
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    make_figure()
