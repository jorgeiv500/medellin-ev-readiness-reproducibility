"""
Storyline evidence figure for the Cities paper.

The figure is deliberately simple: observed baseline evidence, the access
surface implied by that evidence, and the after-expansion lead pool that still
requires field and utility validation.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


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
INNER_EDGE = "#ffffff"
BOUNDARY = "#3f4852"
GRID = "#d8dde3"
SOFT_FILL = "#f5f7f8"

SOURCE_STYLES = {"CargaME": ("#4f8583", "o"), "EPM": ("#ad6f82", "s"), "OSM": ("#806f9f", "^")}
SOURCE_COLORS = {source: style[0] for source, style in SOURCE_STYLES.items()}
ACCESS_CMAP = LinearSegmentedColormap.from_list("access", ["#fbfdfc", "#e6f0ee", "#c8ddd9", "#94beba", "#4f8583"])
OPP_CMAP = LinearSegmentedColormap.from_list("opportunity", ["#fbfcfd", "#e5eef4", "#c7dae6", "#8fb1c9", "#5e829e"])
TYPE_LABELS = {
    "public_facility": "Public facilities",
    "commercial_or_activity_anchor": "Activity anchors",
    "parking": "Parking",
    "education": "Education",
    "fuel_station": "Fuel stations",
    "university": "Universities",
    "centrality": "Centralities",
    "sitva_node": "SITVA nodes",
}


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.0,
            "axes.titlesize": 7.4,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.3,
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
    from matplotlib.colors import LightSource

    shade = LightSource(azdeg=315, altdeg=45).hillshade(z, vert_exag=0.8, dx=1, dy=1)
    extent = (
        lon0 + col0 / 3600,
        lon0 + (col1 - 1) / 3600,
        lat_top - (row1 - 1) / 3600,
        lat_top - row0 / 3600,
    )
    return shade, extent


SHADE, SHADE_EXTENT = hillshade()


def set_map(ax):
    ax.set_facecolor(PAGE)
    ax.set_xlim(BBOX[0], BBOX[2])
    ax.set_ylim(BBOX[1], BBOX[3])
    ax.set_aspect("equal")
    ax.set_axis_off()
    if SHADE is not None and SHADE_EXTENT is not None:
        ax.imshow(SHADE, extent=SHADE_EXTENT, cmap="Greys", alpha=0.10, origin="upper", zorder=0)


def panel_header(ax, number: str, title: str, subtitle: str) -> None:
    ax.text(
        0.0,
        1.080,
        f"{number}. {title}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.6,
        fontweight="semibold",
        color=INK,
        clip_on=False,
    )
    ax.text(
        0.0,
        1.025,
        subtitle,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=6.7,
        color=MUTED,
        clip_on=False,
    )


def access_swatch(ax) -> None:
    x0, y0, w, h = 0.035, 0.040, 0.060, 0.018
    for n, value in enumerate(np.linspace(0.10, 0.95, 5)):
        ax.add_patch(
            Rectangle(
                (x0 + n * w, y0),
                w,
                h,
                transform=ax.transAxes,
                facecolor=ACCESS_CMAP(value),
                edgecolor="none",
                zorder=20,
            )
        )
    ax.text(x0, y0 - 0.012, "low", transform=ax.transAxes, ha="left", va="top", fontsize=5.9, color=MUTED, zorder=21)
    ax.text(x0 + 5 * w, y0 - 0.012, "high access", transform=ax.transAxes, ha="right", va="top", fontsize=5.9, color=MUTED, zorder=21)


def parse_epm() -> pd.DataFrame:
    path = RAW / "chargers" / "epm_public_charging_use_2019_2025.csv"
    df = pd.read_csv(path)
    df["total_raw"] = pd.to_numeric(df["total"], errors="coerce")
    df["total_nonnegative"] = df["total_raw"].clip(lower=0)
    df["negative_flag"] = df["total_raw"] < 0
    q1, q3 = df["total_nonnegative"].quantile([0.25, 0.75])
    df["high_flag"] = df["total_nonnegative"] > q3 + 1.5 * (q3 - q1)
    return df


def evidence_after_panel(ax, chargers, candidates, epm):
    ax.set_facecolor(PAGE)
    ax.set_axis_off()
    panel_header(ax, "3", "After leads", "candidate pool for scenario selection, not approved works")

    metrics = [
        (f"{len(chargers)}", "mapped sites"),
        (f"{len(epm)}", "EPM rows"),
        (f"{len(candidates):,}", "validation leads"),
    ]
    ax.add_patch(Rectangle((0.00, 0.845), 0.98, 0.110, transform=ax.transAxes, facecolor=SOFT_FILL, edgecolor=GRID, linewidth=0.7))
    for i, (value, label) in enumerate(metrics):
        x = 0.035 + i * 0.315
        ax.text(x, 0.912, value, transform=ax.transAxes, ha="left", va="center", fontsize=12.0, fontweight="bold", color=INK)
        ax.text(x, 0.865, label, transform=ax.transAxes, ha="left", va="center", fontsize=6.6, color=MUTED)
        if i < len(metrics) - 1:
            ax.plot([x + 0.255, x + 0.255], [0.865, 0.925], transform=ax.transAxes, color=GRID, linewidth=0.7)

    counts_path = TABLES / "table_counterfactual_candidate_universe.csv"
    if counts_path.exists():
        counts = pd.read_csv(counts_path).sort_values("candidates", ascending=False)
    else:
        counts = (
            candidates.get("candidate_type", pd.Series(["candidate"] * len(candidates)))
            .value_counts()
            .rename_axis("candidate_type")
            .reset_index(name="candidates")
        )
    counts["label"] = counts["candidate_type"].map(TYPE_LABELS).fillna(counts["candidate_type"].str.replace("_", " ", regex=False).str.title())

    ax.text(0.00, 0.775, "Candidate universe used by the after scenarios", transform=ax.transAxes, ha="left", va="center", fontsize=8.0, fontweight="semibold", color=INK)
    max_count = float(counts["candidates"].max()) if not counts.empty else 1.0
    y0 = 0.715
    step = 0.052
    for n, (_, row) in enumerate(counts.head(8).iterrows()):
        y = y0 - n * step
        width = 0.370 * float(row["candidates"]) / max_count
        ax.text(0.00, y, row["label"], transform=ax.transAxes, ha="left", va="center", fontsize=6.9, color=INK)
        ax.add_patch(Rectangle((0.505, y - 0.015), width, 0.028, transform=ax.transAxes, facecolor="#8aa8ba", edgecolor="none"))
        ax.text(0.935, y, f"{int(row['candidates']):,}", transform=ax.transAxes, ha="right", va="center", fontsize=6.9, color=INK)

    ax.plot([0.00, 0.98], [0.250, 0.250], transform=ax.transAxes, color=GRID, linewidth=0.8)
    ax.text(0.00, 0.205, "Evidence boundary", transform=ax.transAxes, ha="left", va="center", fontsize=8.0, fontweight="semibold", color=INK)
    ax.text(
        0.00,
        0.150,
        "EPM confirms public activity "
        f"({epm['total_nonnegative'].sum() / 1_000_000:.2f}M nonnegative disclosed total; "
        f"{int(epm['negative_flag'].sum())} anomaly rows).\n"
        "It does not certify connector uptime, failed starts, queueing,\n"
        "tariffs, payment access, or buildability.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.8,
        color=MUTED,
        linespacing=1.22,
    )


def write_evidence_table(chargers, candidates, epm, zones):
    with (TABLES / "table_cities_evidence_stack.tex").open("w", encoding="utf-8") as fh:
        fh.write("\\begin{tabularx}{\\textwidth}{p{0.18\\textwidth}p{0.14\\textwidth}XX}\n")
        fh.write("\\toprule\nEvidence layer & Observed size & Analytical use & Validation boundary \\\\\n\\midrule\n")
        fh.write(
            f"Mapped public charging & {len(chargers)} records & Reconciles CargaME, EPM, and OSM evidence into the baseline supply layer. & Confirms mapped evidence, not real-time status, connector uptime, queues, tariff access, or payment conditions. \\\\\n"
        )
        fh.write(
            f"EPM public-use disclosure & {len(epm)} monthly rows & Confirms disclosed public activity from January 2019 to June 2025 and flags source anomalies. & Aggregate use table; not connector-level sessions, failed starts, occupancy, or reliability history. \\\\\n"
        )
        fh.write(
            f"Mobility, terrain, and vulnerability & {len(zones)} OD/SIT zones & Links road-network access, slope, home-charging constraint, mobility pressure, and social vulnerability. & Diagnostic planning scale; not parcel, curb, parking-operation, or construction feasibility. \\\\\n"
        )
        fh.write(
            "Activity and intermodal anchors & SITVA, GTFS, centralities & Identifies where charging could connect to everyday destinations and public-transport centrality. & Co-location opportunity only; does not imply transit ridership effects or operator approval. \\\\\n"
        )
        fh.write(
            f"After-expansion candidates & {len(candidates):,} validation leads & Screens public facilities, activity anchors, parking, education, fuel stations, universities, centralities, and SITVA nodes. & Candidate lead pool, not a deployment list; field, utility, safety, tariff, and permit review remain required. \\\\\n"
        )
        fh.write("\\bottomrule\n\\end{tabularx}\n")


def update_manifest():
    manifest_path = TABLES / "figure_manifest.csv"
    row = pd.DataFrame(
        [
            {
                "file": "fig_cities03_supply_use_opportunity.png",
                "role": "evidence-geography",
                "figure": "fig_cities03_supply_use_opportunity.png",
                "status": "generated",
                "description": "Single-map evidence geography linking baseline access, observed charging records, SITVA, and the after-expansion validation lead field.",
            }
        ]
    )
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        key = "file" if "file" in manifest.columns else "figure"
        manifest = manifest[manifest[key] != "fig_cities03_supply_use_opportunity.png"]
        manifest = pd.concat([manifest, row], ignore_index=True)
    else:
        manifest = row
    manifest.to_csv(manifest_path, index=False)


def main():
    setup()
    zones = read_geo(PROCESSED / "readiness_story_screen.gpkg")
    chargers = read_geo(PROCESSED / "mapped_charger_evidence.gpkg")
    candidates = read_geo(PROCESSED / "counterfactual_candidate_universe.gpkg")
    transit = read_geo(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson")
    epm = parse_epm()

    fig, ax = plt.subplots(figsize=(7.15, 7.05), facecolor=PAGE)
    fig.subplots_adjust(left=0.025, right=0.985, top=0.985, bottom=0.115)
    set_map(ax)
    norm = Normalize(0, 1)
    zones.plot(ax=ax, column="access_screen", cmap=ACCESS_CMAP, norm=norm, linewidth=0.20, edgecolor=INNER_EDGE, zorder=2)
    if not candidates.empty:
        candidates.plot(ax=ax, marker=".", color="#6f7f8d", markersize=3.0, alpha=0.22, zorder=4)
    if not transit.empty:
        transit.plot(ax=ax, color=INK, linewidth=1.05, alpha=0.86, zorder=5)
    for source, (color, marker) in SOURCE_STYLES.items():
        subset = chargers[chargers["source"].eq(source)]
        if not subset.empty:
            subset.plot(ax=ax, marker=marker, color=color, markersize=24, edgecolor=PAGE, linewidth=0.45, zorder=7)
    zones.boundary.plot(ax=ax, color=BOUNDARY, linewidth=0.16, alpha=0.44, zorder=6)

    sm = plt.cm.ScalarMappable(norm=norm, cmap=ACCESS_CMAP)
    sm.set_array([])
    cax = fig.add_axes([0.205, 0.066, 0.590, 0.018])
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=6.4, length=0, pad=1)
    cb.set_label("baseline network-reachable public-charging access", fontsize=6.9, color=INK, labelpad=2)

    ax.text(
        0.035,
        0.950,
        "Observed supply",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.8,
        fontweight="semibold",
        color=INK,
    )
    ax.text(
        0.610,
        0.235,
        "Validation leads",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.8,
        fontweight="semibold",
        color=INK,
    )
    ax.text(
        0.035,
        0.125,
        "Evidence boundary",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.8,
        fontweight="semibold",
        color=INK,
    )

    ax.legend(
        handles=[
            Line2D([0], [0], color=INK, linewidth=1.2, label="SITVA"),
            Line2D([0], [0], marker=".", linestyle="", color="#6f7f8d", markersize=6, alpha=0.70, label="candidate leads"),
            *[
                Line2D([0], [0], marker=marker, linestyle="", markerfacecolor=color, markeredgecolor=PAGE, label=source)
                for source, (color, marker) in SOURCE_STYLES.items()
            ],
        ],
        loc="upper right",
        frameon=True,
        facecolor=PAGE,
        edgecolor=GRID,
        framealpha=0.94,
        borderpad=0.35,
        handlelength=1.4,
        handletextpad=0.45,
        fontsize=5.8,
    )

    out = FIGURES / "fig_cities03_supply_use_opportunity.png"
    fig.savefig(out, bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)
    write_evidence_table(chargers, candidates, epm, zones)
    update_manifest()
    print(f"Wrote {out.relative_to(ROOT)}")
    print(f"Wrote {(TABLES / 'table_cities_evidence_stack.tex').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
