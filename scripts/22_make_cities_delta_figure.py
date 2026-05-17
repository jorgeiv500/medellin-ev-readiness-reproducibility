"""
Baseline-to-proposal delta figure for the Cities manuscript.

The figure isolates the editorial question that the atlas cannot show cleanly:
which zones move after expansion, and whether market-ready and equity-transition
rules move the same territories.
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
MARKET = "#6f8793"
EQUITY = "#b57462"

BASELINE_CMAP = LinearSegmentedColormap.from_list(
    "baseline_trap", ["#fbfaf6", "#f1e7de", "#dec9b9", "#c99680", "#96604f"]
)
GAIN_CMAP = LinearSegmentedColormap.from_list(
    "proposal_gain", ["#fbfaf6", "#e8f1ed", "#c7ddd6", "#8bb9ac", "#477f78"]
)
DIFF_CMAP = LinearSegmentedColormap.from_list(
    "equity_market_difference", [MARKET, "#fbfaf6", EQUITY]
)


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 6.3,
            "axes.titlesize": 7.0,
            "legend.fontsize": 5.9,
            "savefig.dpi": 360,
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


def add_colorbar(ax, cmap, norm, label: str, xpos: float = 0.18, width: float = 0.58) -> None:
    fig = ax.figure
    pos = ax.get_position()
    cax = fig.add_axes(
        [
            pos.x0 + pos.width * xpos,
            pos.y0 - 0.032,
            pos.width * width,
            0.011,
        ]
    )
    cax.set_facecolor(PAGE)
    cb = plt.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=5.1, length=0, pad=1)
    cb.set_label(label, fontsize=5.4, color=MUTED, labelpad=1)


def plot_context(ax, layer: gpd.GeoDataFrame, transit: gpd.GeoDataFrame, trap_zones: gpd.GeoDataFrame) -> None:
    layer.plot(ax=ax, color="#f3f2ec", edgecolor=EDGE, linewidth=0.18, zorder=1)
    if not transit.empty:
        transit.plot(ax=ax, color=TRANSIT, linewidth=0.74, alpha=0.72, zorder=4)
    if not trap_zones.empty:
        trap_zones.boundary.plot(ax=ax, color=TRAP_EDGE, linewidth=0.48, alpha=0.90, zorder=5)


def plot_selected(ax, selected: gpd.GeoDataFrame, scenario: str, color: str, marker: str) -> None:
    subset = selected[selected["scenario"].eq(scenario)]
    if subset.empty:
        return
    subset.plot(
        ax=ax,
        marker=marker,
        color=color,
        markersize=18,
        edgecolor=PAGE,
        linewidth=0.45,
        alpha=0.96,
        zorder=8,
    )


def update_manifest(filename: str) -> None:
    row = pd.DataFrame(
        [
            {
                "file": filename,
                "role": "proposal-delta",
                "figure": filename,
                "status": "generated",
                "description": "Baseline-to-proposal delta maps comparing market-ready and equity-transition rule effects.",
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
    transit = clip(read_geo(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson"))

    base = outcomes[outcomes["scenario"].eq("equity_transition")].copy()
    market = outcomes[outcomes["scenario"].eq("market_ready")].copy()
    equity = outcomes[outcomes["scenario"].eq("equity_transition")].copy()

    trap_threshold = base["disadvantage_before"].quantile(0.75)
    trap_zones = base[base["disadvantage_before"] >= trap_threshold].copy()

    baseline_norm = Normalize(0, float(base["disadvantage_before"].quantile(0.98)))
    gain_max = float(max(market["disadvantage_reduction"].quantile(0.98), equity["disadvantage_reduction"].quantile(0.98)))
    gain_norm = Normalize(0, gain_max)

    diff = equity[["zone_id", "geometry", "disadvantage_reduction"]].rename(
        columns={"disadvantage_reduction": "equity_gain"}
    )
    market_gain = market[["zone_id", "disadvantage_reduction"]].rename(
        columns={"disadvantage_reduction": "market_gain"}
    )
    diff = diff.merge(market_gain, on="zone_id", how="left")
    diff["equity_minus_market"] = diff["equity_gain"] - diff["market_gain"]
    diff_abs = float(np.nanquantile(np.abs(diff["equity_minus_market"]), 0.98))
    diff_norm = TwoSlopeNorm(vmin=-diff_abs, vcenter=0, vmax=diff_abs)

    fig, axes = plt.subplots(2, 2, figsize=(7.45, 6.20), facecolor=PAGE)
    fig.subplots_adjust(left=0.025, right=0.990, top=0.965, bottom=0.118, wspace=0.040, hspace=0.255)
    ax_base, ax_market, ax_equity, ax_diff = axes.ravel()

    set_map(ax_base)
    base.plot(
        ax=ax_base,
        column="disadvantage_before",
        cmap=BASELINE_CMAP,
        norm=baseline_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=2,
    )
    plot_context(ax_base, base, transit, trap_zones)
    base.plot(
        ax=ax_base,
        column="disadvantage_before",
        cmap=BASELINE_CMAP,
        norm=baseline_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=3,
    )
    trap_zones.boundary.plot(ax=ax_base, color=TRAP_EDGE, linewidth=0.55, zorder=6)
    ax_base.set_title("(a) inherited baseline trap", loc="left", fontweight="semibold", color=INK, pad=2)
    add_colorbar(ax_base, BASELINE_CMAP, baseline_norm, "baseline readiness-trap score")

    set_map(ax_market)
    plot_context(ax_market, market, transit, trap_zones)
    market.plot(
        ax=ax_market,
        column="disadvantage_reduction",
        cmap=GAIN_CMAP,
        norm=gain_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=3,
    )
    plot_selected(ax_market, selected, "market_ready", MARKET, "s")
    ax_market.set_title("(b) change under market-ready rule", loc="left", fontweight="semibold", color=INK, pad=2)

    set_map(ax_equity)
    plot_context(ax_equity, equity, transit, trap_zones)
    equity.plot(
        ax=ax_equity,
        column="disadvantage_reduction",
        cmap=GAIN_CMAP,
        norm=gain_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=3,
    )
    plot_selected(ax_equity, selected, "equity_transition", EQUITY, "D")
    ax_equity.set_title("(c) change under equity-transition rule", loc="left", fontweight="semibold", color=INK, pad=2)
    add_colorbar(ax_equity, GAIN_CMAP, gain_norm, "reduction in readiness-trap score")

    set_map(ax_diff)
    plot_context(ax_diff, diff, transit, trap_zones)
    diff.plot(
        ax=ax_diff,
        column="equity_minus_market",
        cmap=DIFF_CMAP,
        norm=diff_norm,
        edgecolor=EDGE,
        linewidth=0.20,
        zorder=3,
    )
    ax_diff.set_title("(d) equity-minus-market gain", loc="left", fontweight="semibold", color=INK, pad=2)
    add_colorbar(ax_diff, DIFF_CMAP, diff_norm, "negative: market-ready higher; positive: equity-transition higher", xpos=0.08, width=0.78)

    handles = [
        Line2D([0], [0], color=TRANSIT, lw=1.0, label="SITVA/Metro"),
        Patch(facecolor="none", edgecolor=TRAP_EDGE, linewidth=0.8, label="baseline top-trap quartile"),
        Line2D([0], [0], marker="s", linestyle="", markerfacecolor=MARKET, markeredgecolor=PAGE, markersize=4.8, label="market-ready lead"),
        Line2D([0], [0], marker="D", linestyle="", markerfacecolor=EQUITY, markeredgecolor=PAGE, markersize=4.8, label="equity-transition lead"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.50, 0.018),
        columnspacing=1.4,
        handletextpad=0.45,
        fontsize=6.0,
    )

    out = FIGURES / "fig_cities04_baseline_proposal_delta.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    update_manifest(out.name)
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    make_figure()
