"""
Methodological diagram for the Cities manuscript.

The figure is a diagram, not a map panel and not a dashboard. It explains the
method as a public-data planning screen: evidence assembly, baseline-trap
construction, scenario design, residual evaluation, and methodological guards.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import pandas as pd
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
PROCESSED = ROOT / "data_processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

WGS84 = "EPSG:4326"
METRIC = "EPSG:3116"

PAGE = "#fbfaf6"
INK = "#263034"
MUTED = "#68736f"
EDGE = "#fffdf8"
FRAME = "#5f6865"
LIGHT_FRAME = "#b9b4a8"
BASE_FILL = "#f3f2ec"
BOX_FILL = "#fffdf8"
ROAD = "#d2cdc1"
TRANSIT = "#2f3a3e"
CANDIDATE = "#8c938e"

TRAP_CMAP = LinearSegmentedColormap.from_list(
    "method_trap",
    ["#fbfaf6", "#f1e7de", "#dec9b9", "#c99680", "#96604f"],
)
ACCESS_CMAP = LinearSegmentedColormap.from_list(
    "method_access",
    ["#fbfaf6", "#eaf1eb", "#cddfd3", "#96bdae", "#557f78"],
)

CHARGER_COLORS = {
    "CargaME": "#557f78",
    "EPM": "#b57462",
    "OSM": "#7a768f",
}


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 6.2,
            "axes.titlesize": 7.1,
            "axes.labelsize": 6.4,
            "xtick.labelsize": 5.8,
            "ytick.labelsize": 5.8,
            "legend.fontsize": 5.8,
            "savefig.dpi": 360,
            "axes.linewidth": 0.55,
        }
    )
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)


def read_geo(path: Path) -> gpd.GeoDataFrame:
    if not path.exists() or path.stat().st_size < 100:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    gdf = gpd.read_file(path)
    gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf


def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf.set_crs(WGS84, allow_override=True).to_crs(METRIC)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(METRIC)


def padded_bounds(gdf: gpd.GeoDataFrame, pad: float = 0.035) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = gdf.total_bounds
    dx, dy = maxx - minx, maxy - miny
    return minx - pad * dx, miny - pad * dy, maxx + pad * dx, maxy + pad * dy


def clip(gdf: gpd.GeoDataFrame, bds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    minx, miny, maxx, maxy = bds
    return to_metric(gdf).cx[minx:maxx, miny:maxy].copy()


def set_map(ax: plt.Axes, bds: tuple[float, float, float, float]) -> None:
    ax.set_xlim(bds[0], bds[2])
    ax.set_ylim(bds[1], bds[3])
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_facecolor(PAGE)


def plot_context(ax: plt.Axes, zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, transit: gpd.GeoDataFrame, bds: tuple[float, float, float, float]) -> None:
    z = clip(zones, bds)
    if not z.empty:
        z.plot(ax=ax, color=BASE_FILL, edgecolor="#d2d8de", linewidth=0.18, zorder=1)
    r = clip(roads, bds)
    if not r.empty:
        r.plot(ax=ax, color=ROAD, linewidth=0.24, alpha=0.48, zorder=3)
    t = clip(transit, bds)
    if not t.empty:
        t.plot(ax=ax, color=TRANSIT, linewidth=0.70, alpha=0.72, zorder=5)


def plot_chargers(ax: plt.Axes, chargers: gpd.GeoDataFrame) -> None:
    if chargers.empty:
        return
    c = to_metric(chargers)
    for source, color in CHARGER_COLORS.items():
        layer = c[c.get("source", "").astype(str).str.contains(source, case=False, na=False)]
        if not layer.empty:
            layer.plot(ax=ax, marker="o", color=color, markersize=13, edgecolor=PAGE, linewidth=0.35, alpha=0.92, zorder=8)


def plot_metric_map(
    ax: plt.Axes,
    zones: gpd.GeoDataFrame,
    column: str,
    norm: Normalize,
    cmap,
    bds: tuple[float, float, float, float],
    high_traps: gpd.GeoDataFrame | None = None,
) -> None:
    set_map(ax, bds)
    z = clip(zones, bds)
    if not z.empty and column in z.columns:
        z.plot(ax=ax, column=column, cmap=cmap, norm=norm, edgecolor=EDGE, linewidth=0.22, zorder=2)
    if high_traps is not None and not high_traps.empty:
        clip(high_traps, bds).boundary.plot(ax=ax, color=FRAME, linewidth=0.48, zorder=6)


def journal_panel(ax: plt.Axes, label: str, title: str, subtitle: str | None = None) -> None:
    ax.add_patch(
        Rectangle(
            (0, 0),
            1,
            1,
            transform=ax.transAxes,
            facecolor="none",
            edgecolor=FRAME,
            linewidth=0.58,
            zorder=20,
            clip_on=False,
        )
    )
    ax.text(0.000, 1.055, f"{label} {title}", transform=ax.transAxes, ha="left", va="bottom", fontsize=6.45, fontweight="semibold", color=INK)
    if subtitle:
        ax.text(0.115, 1.000, subtitle, transform=ax.transAxes, ha="left", va="bottom", fontsize=5.2, color=MUTED)


def text_panel(ax: plt.Axes, label: str, title: str, rows: list[tuple[str, str]]) -> None:
    ax.set_axis_off()
    ax.add_patch(
        Rectangle(
            (0, 0),
            1,
            1,
            transform=ax.transAxes,
            facecolor=PAGE,
            edgecolor=FRAME,
            linewidth=0.58,
            zorder=2,
            clip_on=False,
        )
    )
    ax.text(0.000, 1.055, f"{label} {title}", transform=ax.transAxes, ha="left", va="bottom", fontsize=6.45, fontweight="semibold", color=INK)
    y = 0.800
    for head, body in rows:
        ax.text(0.060, y, head, transform=ax.transAxes, ha="left", va="center", fontsize=5.65, fontweight="semibold", color=INK)
        ax.text(0.325, y, body, transform=ax.transAxes, ha="left", va="center", fontsize=5.05, color=MUTED)
        y -= 0.150


def add_module(
    fig: plt.Figure,
    x: float,
    y: float,
    w: float,
    label: str,
    title: str,
    rows: list[tuple[str, str]],
    formula: str | None = None,
) -> None:
    fig.lines.append(
        Line2D([x, x + w], [y + 0.170, y + 0.170], transform=fig.transFigure, color=FRAME, linewidth=0.58)
    )
    fig.text(x, y + 0.188, f"{label} {title}", ha="left", va="bottom", fontsize=6.45, fontweight="semibold", color=INK)
    row_y = y + 0.126
    for head, body in rows:
        fig.text(x + 0.004, row_y, head, ha="left", va="center", fontsize=5.25, fontweight="semibold", color=INK)
        fig.text(x + 0.105, row_y, body, ha="left", va="center", fontsize=5.10, color=MUTED)
        row_y -= 0.035
    if formula:
        fig.text(x + 0.004, row_y - 0.010, formula, ha="left", va="bottom", fontsize=5.45, color=INK)


def curved_arrow(fig: plt.Figure, start: tuple[float, float], end: tuple[float, float], rad: float) -> None:
    fig.add_artist(
        FancyArrowPatch(
            start,
            end,
            transform=fig.transFigure,
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle="-|>",
            mutation_scale=8.5,
            linewidth=0.52,
            color=LIGHT_FRAME,
            shrinkA=2,
            shrinkB=2,
        )
    )


def add_box(fig: plt.Figure, x: float, y: float, w: float, h: float, label: str, title: str, subtitle: str | None = None) -> None:
    fig.add_artist(
        Rectangle(
            (x, y),
            w,
            h,
            transform=fig.transFigure,
            facecolor=BOX_FILL,
            edgecolor=FRAME,
            linewidth=0.66,
            zorder=-5,
        )
    )
    fig.text(x + 0.012, y + h - 0.038, f"{label} {title}", ha="left", va="top", fontsize=6.6, fontweight="semibold", color=INK)
    if subtitle:
        fig.text(x + 0.012, y + h - 0.066, subtitle, ha="left", va="top", fontsize=5.15, color=MUTED)


def add_rows(
    fig: plt.Figure,
    x: float,
    y: float,
    rows: list[tuple[str, str]],
    col2: float = 0.090,
    dy: float = 0.034,
    body_size: float = 5.0,
) -> None:
    for idx, (head, body) in enumerate(rows):
        yy = y - idx * dy
        fig.text(x, yy, head, ha="left", va="center", fontsize=5.10, fontweight="semibold", color=INK)
        fig.text(x + col2, yy, body, ha="left", va="center", fontsize=body_size, color=MUTED)


def add_map_frame(ax: plt.Axes) -> None:
    ax.add_patch(
        Rectangle(
            (0, 0),
            1,
            1,
            transform=ax.transAxes,
            facecolor="none",
            edgecolor=FRAME,
            linewidth=0.62,
            zorder=25,
            clip_on=False,
        )
    )


def compact_map(
    ax: plt.Axes,
    zones: gpd.GeoDataFrame,
    column: str,
    norm: Normalize,
    cmap,
    bds: tuple[float, float, float, float],
    high_traps: gpd.GeoDataFrame | None = None,
) -> None:
    plot_metric_map(ax, zones, column, norm, cmap, bds, high_traps)
    add_map_frame(ax)


def update_manifest(filename: str) -> None:
    row = pd.DataFrame(
        [
            {
                "file": filename,
                "role": "methodological-design",
                "figure": filename,
                "status": "generated",
                "description": "Methodological city-field linking public evidence, baseline traps, candidate validation leads and after-expansion residual interpretation.",
            }
        ]
    )
    manifest_path = TABLES / "figure_manifest.csv"
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        key = "file" if "file" in manifest.columns else "figure"
        manifest = manifest[manifest[key] != filename]
        manifest = pd.concat([row, manifest], ignore_index=True)
    else:
        manifest = row
    manifest.to_csv(manifest_path, index=False)


def make_figure() -> None:
    setup()

    zones = read_geo(PROCESSED / "readiness_story_screen.gpkg")
    chargers = read_geo(PROCESSED / "mapped_charger_evidence.gpkg")
    candidates = read_geo(PROCESSED / "counterfactual_candidate_universe.gpkg")
    selected = read_geo(PROCESSED / "counterfactual_selected_sites.gpkg")
    outcomes = read_geo(PROCESSED / "counterfactual_zone_outcomes.gpkg")

    if zones.empty:
        raise RuntimeError("Missing readiness_story_screen.gpkg; run the story-map pipeline first.")

    charger_count = len(chargers)
    candidate_count = len(candidates)

    fig = plt.figure(figsize=(8.6, 4.65), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()

    line = "#333333"
    data_fill = "#ffffff"
    top_fill = "#edf5e8"
    bottom_fill = "#e5f4f8"
    light_line = "#8a8a8a"

    def add_rect(
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str = data_fill,
        edge: str = line,
        lw: float = 0.7,
        ls: str = "-",
    ) -> None:
        ax.add_patch(
            Rectangle(
                (x, y),
                w,
                h,
                transform=ax.transAxes,
                facecolor=fill,
                edgecolor=edge,
                linewidth=lw,
                linestyle=ls,
                zorder=1,
            )
        )

    def add_text(
        x: float,
        y: float,
        text: str,
        size: float = 6.0,
        color: str = line,
        weight: str = "normal",
        ha: str = "center",
        va: str = "center",
    ) -> None:
        fig.text(x, y, text, ha=ha, va=va, fontsize=size, color=color, fontweight=weight, linespacing=1.08)

    def arrow(start: tuple[float, float], end: tuple[float, float], rad: float = 0.0, color: str = line) -> None:
        fig.add_artist(
            FancyArrowPatch(
                start,
                end,
                transform=fig.transFigure,
                connectionstyle=f"arc3,rad={rad}",
                arrowstyle="-|>",
                mutation_scale=8.5,
                linewidth=0.75,
                color=color,
                shrinkA=1,
                shrinkB=1,
            )
        )

    def group_box(x: float, y: float, w: float, h: float, title: str) -> None:
        add_rect(x, y, w, h, fill=data_fill, edge=line, lw=0.7)
        add_text(x + w / 2, y + h - 0.024, title, size=5.35, weight="semibold")

    def inner_box(x: float, y: float, w: float, h: float, text: str, size: float = 5.5, weight: str = "normal") -> None:
        add_rect(x, y, w, h, fill=data_fill, edge=line, lw=0.55)
        add_text(x + w / 2, y + h / 2, text, size=size, weight=weight)

    # Left data stack for the evidence base.
    lx, lw = 0.055, 0.270
    group_box(lx, 0.820, lw, 0.090, "Charging evidence")
    add_text(lx + lw / 2, 0.854, f"{charger_count} mapped public-charging records\nCargaME, EPM and OSM evidence", size=4.15)

    group_box(lx, 0.610, lw, 0.180, "Mobility and network data")
    inner_box(lx + 0.018, 0.695, 0.072, 0.052, "OD/SIT\nzones", size=4.10)
    inner_box(lx + 0.018, 0.632, 0.072, 0.052, "road\nnetwork", size=4.10)
    add_rect(lx + 0.130, 0.627, 0.118, 0.130, fill=data_fill, edge=line, lw=0.50, ls=(0, (3, 2)))
    inner_box(lx + 0.145, 0.709, 0.088, 0.033, "drive time", size=4.05)
    inner_box(lx + 0.145, 0.669, 0.088, 0.033, "SITVA anchors", size=4.05)
    inner_box(lx + 0.145, 0.629, 0.088, 0.033, "activity anchors", size=4.05)
    arrow((lx + 0.092, 0.721), (lx + 0.130, 0.706), color=light_line)
    arrow((lx + 0.092, 0.658), (lx + 0.130, 0.669), color=light_line)

    group_box(lx, 0.395, lw, 0.155, "Urban constraint data")
    inner_box(lx + 0.018, 0.465, 0.084, 0.046, "slope and\nelevation", size=4.05)
    inner_box(lx + 0.018, 0.412, 0.084, 0.046, "ECV/social\nevidence", size=4.05)
    add_rect(lx + 0.132, 0.405, 0.112, 0.112, fill=data_fill, edge=line, lw=0.50, ls=(0, (3, 2)))
    inner_box(lx + 0.145, 0.472, 0.086, 0.029, "home constraint", size=3.95)
    inner_box(lx + 0.145, 0.438, 0.086, 0.029, "vulnerability", size=3.95)
    inner_box(lx + 0.145, 0.404, 0.086, 0.029, "mobility pressure", size=3.95)
    arrow((lx + 0.104, 0.488), (lx + 0.132, 0.488), color=light_line)
    arrow((lx + 0.104, 0.435), (lx + 0.132, 0.438), color=light_line)

    group_box(lx, 0.145, lw, 0.180, "Candidate and validation data")
    inner_box(lx + 0.018, 0.235, 0.083, 0.043, "public\nfacilities", size=4.00)
    inner_box(lx + 0.111, 0.235, 0.078, 0.043, "activity\nanchors", size=4.00)
    inner_box(lx + 0.199, 0.235, 0.050, 0.043, "SITVA", size=4.00)
    add_rect(lx + 0.050, 0.152, 0.180, 0.078, fill=data_fill, edge=line, lw=0.50, ls=(0, (3, 2)))
    inner_box(lx + 0.064, 0.191, 0.152, 0.028, f"{candidate_count:,} candidate leads", size=3.95)
    inner_box(lx + 0.064, 0.158, 0.152, 0.028, "300 m exclusion screen", size=3.95)

    # Main analysis modules. The structure reads as an urban planning sequence
    # rather than a computational pipeline.
    rx, rw = 0.355, 0.590
    top_y, top_h = 0.535, 0.375
    bottom_y, bottom_h = 0.145, 0.330
    add_rect(rx, top_y, rw, top_h, fill=top_fill, edge=line, lw=0.75)
    add_text(rx + rw / 2, top_y + top_h - 0.030, "Baseline construction and scenario design", size=5.85, weight="semibold")

    inner_box(rx + 0.025, top_y + 0.245, 0.218, 0.055, "Baseline readiness trap", size=4.90, weight="semibold")
    inner_box(rx + 0.035, top_y + 0.205, 0.198, 0.032, "access failure", size=4.30)
    inner_box(rx + 0.035, top_y + 0.166, 0.198, 0.032, "transition pressure", size=4.30)
    inner_box(rx + 0.035, top_y + 0.127, 0.198, 0.032, "home, slope, vulnerability", size=4.30)

    inner_box(rx + 0.338, top_y + 0.245, 0.218, 0.055, "Scenario rules", size=4.90, weight="semibold")
    inner_box(rx + 0.348, top_y + 0.205, 0.198, 0.032, "3,820 validation leads", size=4.30)
    inner_box(rx + 0.348, top_y + 0.166, 0.198, 0.032, "five governance logics", size=4.30)
    inner_box(rx + 0.348, top_y + 0.127, 0.198, 0.032, "20 selected leads each", size=4.30)

    inner_box(rx + 0.025, top_y + 0.035, 0.218, 0.075, "Before condition\ninherited disadvantage", size=4.55, weight="semibold")
    inner_box(rx + 0.338, top_y + 0.035, 0.218, 0.075, "After condition\nrule-specific residual", size=4.55, weight="semibold")

    arrow((rx + 0.243, top_y + 0.222), (rx + 0.338, top_y + 0.222))
    arrow((rx + 0.134, top_y + 0.127), (rx + 0.134, top_y + 0.110))
    arrow((rx + 0.447, top_y + 0.127), (rx + 0.447, top_y + 0.110))
    arrow((rx + 0.243, top_y + 0.073), (rx + 0.338, top_y + 0.073))

    add_rect(rx, bottom_y, rw, bottom_h, fill=bottom_fill, edge=line, lw=0.75)
    add_text(rx + rw / 2, bottom_y + bottom_h - 0.030, "Residual evaluation and implementation boundary", size=5.85, weight="semibold")

    inner_box(rx + 0.025, bottom_y + 0.215, 0.205, 0.055, "Residual geographies", size=4.85, weight="semibold")
    inner_box(rx + 0.035, bottom_y + 0.170, 0.185, 0.032, "baseline-to-proposal delta", size=4.25)
    inner_box(rx + 0.035, bottom_y + 0.132, 0.185, 0.032, "zones still underserved", size=4.25)
    inner_box(rx + 0.035, bottom_y + 0.094, 0.185, 0.032, "rule-difference geography", size=4.25)

    inner_box(rx + 0.310, bottom_y + 0.215, 0.245, 0.055, "Policy interpretation", size=4.85, weight="semibold")
    inner_box(rx + 0.320, bottom_y + 0.170, 0.225, 0.032, "not a deployment certificate", size=4.25)
    inner_box(rx + 0.320, bottom_y + 0.132, 0.225, 0.032, "field, utility, tariff and safety checks", size=4.25)
    inner_box(rx + 0.320, bottom_y + 0.094, 0.225, 0.032, "metropolitan governance review", size=4.25)
    inner_box(rx + 0.165, bottom_y + 0.025, 0.250, 0.045, "public charging as urban service, not asset count", size=4.35, weight="semibold")

    arrow((rx + 0.230, bottom_y + 0.242), (rx + 0.310, bottom_y + 0.242))
    arrow((rx + 0.220, bottom_y + 0.148), (rx + 0.320, bottom_y + 0.148))
    arrow((rx + 0.445, bottom_y + 0.094), (rx + 0.415, bottom_y + 0.070))
    arrow((rx + 0.150, bottom_y + 0.094), (rx + 0.210, bottom_y + 0.070))

    # Cross-module arrows from data stack into analytical modules.
    arrow((lx + lw, 0.872), (rx, top_y + 0.272))
    arrow((lx + lw, 0.705), (rx, top_y + 0.225))
    arrow((lx + lw, 0.472), (rx, bottom_y + 0.210))
    arrow((lx + lw, 0.235), (rx, top_y + 0.205))
    arrow((rx + 0.295, top_y), (rx + 0.295, bottom_y + bottom_h))


    out = FIGURES / "fig_cities00_methodological_design.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    update_manifest(out.name)
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    make_figure()
