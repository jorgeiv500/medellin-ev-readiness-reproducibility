"""
Current-city diagnostic atlas for the Cities manuscript.

The first figure has to establish Medellin as an urban infrastructure case
before the paper introduces the readiness baseline or the counterfactual method.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize
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

ACCESS_CMAP = LinearSegmentedColormap.from_list(
    "current_access", ["#fbfaf6", "#eaf1eb", "#cddfd3", "#96bdae", "#557f78"]
)
FRICTION_CMAP = LinearSegmentedColormap.from_list(
    "current_friction", ["#fbfaf6", "#e8ecea", "#d0d9d6", "#a8b8b7", "#71868a"]
)
PRESSURE_CMAP = LinearSegmentedColormap.from_list(
    "current_pressure", ["#fbfaf6", "#f1e7de", "#dec9b9", "#c99680", "#96604f"]
)
CONTEXT_FILL = "#f3f2ec"
ROAD = "#9aa09b"
CENTRALITY = "#6c907f"
SITVA = "#2f3a3e"
SUBSTATION = "#4b5658"
SOURCE_STYLES = {
    "CargaME": ("#557f78", "o"),
    "EPM": ("#b57462", "s"),
    "OSM": ("#7a768f", "^"),
}


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.0,
            "axes.titlesize": 7.4,
            "legend.fontsize": 5.9,
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


def hillshade():
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


def read_substations() -> gpd.GeoDataFrame:
    path = RAW / "electric" / "upme_substations_national_raw.json"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    gdf = read_geo(path)
    if "CAPACIDAD_MVA" in gdf.columns:
        gdf["CAPACIDAD_MVA"] = pd.to_numeric(gdf["CAPACIDAD_MVA"], errors="coerce")
    return clip(gdf)


def set_map(ax) -> None:
    ax.set_facecolor(PAGE)
    ax.set_xlim(BBOX[0], BBOX[2])
    ax.set_ylim(BBOX[1], BBOX[3])
    ax.set_aspect("equal")
    ax.set_axis_off()
    if SHADE is not None and SHADE_EXTENT is not None:
        ax.imshow(SHADE, extent=SHADE_EXTENT, cmap="Greys", alpha=0.08, origin="upper", zorder=0)


def colorbar(fig, ax, cmap, label: str) -> None:
    sm = ScalarMappable(norm=Normalize(0, 1), cmap=cmap)
    sm.set_array([])
    pos = ax.get_position()
    cax = fig.add_axes(
        [
            pos.x0 + pos.width * 0.22,
            pos.y0 - 0.030,
            pos.width * 0.56,
            0.011,
        ]
    )
    cax.set_facecolor(PAGE)
    cb = plt.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=5.2, length=0, pad=1)
    cb.set_label(label, fontsize=5.6, color=INK, labelpad=1)


def plot_context(ax, zones, roads, centralities, transit) -> None:
    zones.plot(ax=ax, color=CONTEXT_FILL, edgecolor=EDGE, linewidth=0.20, zorder=1)
    if SHADE is not None and SHADE_EXTENT is not None:
        ax.imshow(SHADE, extent=SHADE_EXTENT, cmap="Greys", alpha=0.07, origin="upper", zorder=2)
    if not roads.empty:
        roads.plot(ax=ax, color=ROAD, linewidth=0.30, alpha=0.46, zorder=3)
    if not centralities.empty:
        centralities.boundary.plot(ax=ax, color=CENTRALITY, linewidth=0.56, alpha=0.78, zorder=4)
    if not transit.empty:
        transit.plot(ax=ax, color=SITVA, linewidth=1.10, alpha=0.90, zorder=5)


def plot_chargers(ax, chargers, size: int = 25) -> None:
    for source, (color, marker) in SOURCE_STYLES.items():
        subset = chargers[chargers["source"].eq(source)]
        if not subset.empty:
            subset.plot(ax=ax, marker=marker, color=color, markersize=size, edgecolor=PAGE, linewidth=0.45, zorder=8)


def make_figure() -> None:
    setup()
    zones = clip(read_geo(PROCESSED / "readiness_story_screen.gpkg"))
    chargers = clip(read_geo(PROCESSED / "mapped_charger_evidence.gpkg"))
    substations = read_substations()
    centralities = clip(read_geo(RAW / "planning" / "geomedellin" / "centralities.geojson"))
    transit = clip(read_geo(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson"))
    roads = clip(read_geo(RAW / "transport" / "geomedellin" / "road_hierarchy.geojson"))

    fig, axes = plt.subplots(2, 2, figsize=(7.75, 7.30), facecolor=PAGE)
    fig.subplots_adjust(left=0.032, right=0.978, top=0.970, bottom=0.118, wspace=0.010, hspace=0.215)
    axes = axes.ravel()

    ax = axes[0]
    set_map(ax)
    plot_context(ax, zones, roads, centralities, transit)
    if not substations.empty:
        sizes = np.clip(substations.get("CAPACIDAD_MVA", pd.Series(8, index=substations.index)).fillna(8), 4, 120)
        substations.plot(ax=ax, marker="D", color=SUBSTATION, markersize=6 + sizes * 0.20, alpha=0.65, edgecolor=PAGE, linewidth=0.25, zorder=7)
    plot_chargers(ax, chargers, size=26)
    ax.set_title("(a) current charging and electric-support evidence", loc="left", fontweight="semibold", color=INK)

    ax = axes[1]
    set_map(ax)
    zones.plot(ax=ax, column="access_screen", cmap=ACCESS_CMAP, vmin=0, vmax=1, edgecolor=EDGE, linewidth=0.20, zorder=2)
    transit.plot(ax=ax, color=SITVA, linewidth=0.92, alpha=0.82, zorder=4)
    plot_chargers(ax, chargers, size=18)
    ax.set_title("(b) present public-charging reachability", loc="left", fontweight="semibold", color=INK)
    colorbar(fig, ax, ACCESS_CMAP, "network-reachable access")

    ax = axes[2]
    set_map(ax)
    zones.plot(ax=ax, column="topography_burden_screen", cmap=FRICTION_CMAP, vmin=0, vmax=1, edgecolor=EDGE, linewidth=0.20, zorder=2)
    if not roads.empty:
        roads.plot(ax=ax, color="#485357", linewidth=0.22, alpha=0.48, zorder=4)
    zones.boundary.plot(ax=ax, color="#aaa69a", linewidth=0.12, alpha=0.56, zorder=5)
    ax.set_title("(c) topographic burden and road form", loc="left", fontweight="semibold", color=INK)
    colorbar(fig, ax, FRICTION_CMAP, "topographic burden")

    ax = axes[3]
    set_map(ax)
    zones.plot(ax=ax, column="transition_pressure", cmap=PRESSURE_CMAP, vmin=0, vmax=1, edgecolor=EDGE, linewidth=0.20, zorder=2)
    zones[zones["home_constraint_screen"].fillna(0) >= zones["home_constraint_screen"].quantile(0.75)].boundary.plot(
        ax=ax, color=BOUNDARY, linewidth=0.48, alpha=0.78, zorder=5
    )
    ax.set_title("(d) transition pressure before expansion", loc="left", fontweight="semibold", color=INK)
    colorbar(fig, ax, PRESSURE_CMAP, "transition pressure")

    fig.legend(
        handles=[
            Line2D([0], [0], color=SITVA, lw=1.5, label="SITVA"),
            Line2D([0], [0], color=CENTRALITY, lw=0.9, label="centralities"),
            Line2D([0], [0], marker="D", linestyle="", markerfacecolor=SUBSTATION, markeredgecolor=PAGE, markersize=4.5, label="UPME substations"),
            *[
                Line2D([0], [0], marker=marker, linestyle="", markerfacecolor=color, markeredgecolor=PAGE, markersize=5, label=source)
                for source, (color, marker) in SOURCE_STYLES.items()
            ],
            Patch(facecolor="none", edgecolor=BOUNDARY, linewidth=0.8, label="highest home-charging constraint"),
        ],
        loc="lower center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.505, 0.026),
        columnspacing=1.05,
        handlelength=1.30,
        handletextpad=0.42,
        fontsize=5.8,
    )

    out = FIGURES / "fig_cities01_current_city_condition.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)

    manifest_path = TABLES / "figure_manifest.csv"
    row = pd.DataFrame(
        [
            {
                "file": out.name,
                "role": "current-city-condition",
                "figure": out.name,
                "status": "generated",
                "description": "Current urban-infrastructure condition: charging evidence, public electric-support substations, network-reachable access, topographic burden and transition pressure.",
            }
        ]
    )
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        key = "file" if "file" in manifest.columns else "figure"
        manifest = manifest[manifest[key] != out.name]
        manifest = pd.concat([row, manifest], ignore_index=True)
    else:
        manifest = row
    manifest.to_csv(manifest_path, index=False)
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    make_figure()
