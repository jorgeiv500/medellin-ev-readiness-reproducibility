from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from matplotlib import gridspec
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
PROCESSED = ROOT / "data_processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"
WGS84 = "EPSG:4326"
METRIC = "EPSG:3116"
DEFAULT_SPEED_KPH = 28.0
BOUNDS_WGS = (-75.68, 6.12, -75.45, 6.38)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.2,
        "axes.titlesize": 9.2,
        "axes.labelsize": 8.2,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "legend.fontsize": 7.0,
        "axes.linewidth": 0.55,
        "savefig.dpi": 320,
        "figure.facecolor": "white",
    }
)

BASE = {
    "page": "#fbfaf6",
    "canvas": "#f3f2ec",
    "polygon": "#fbfaf6",
    "boundary": "#c8c3b6",
    "road_major": "#8f9690",
    "sitva": "#2f3a3e",
    "cargame": "#557f78",
    "epm": "#b57462",
    "osm": "#7a768f",
    "candidate": "#2f3a3e",
    "text": "#263034",
    "muted": "#68736f",
}

# Soft, print-friendly sequential palettes for the manuscript visual system.
# Access uses blue-green, disadvantage uses wine, and physical/social burdens
# use grey-blue so the page does not read as a brown/ochre map series.
CMAPS = {
    "access": LinearSegmentedColormap.from_list("access", ["#fbfaf6", "#eaf1eb", "#cddfd3", "#96bdae", "#557f78"]),
    "constraint": LinearSegmentedColormap.from_list("constraint", ["#fbfaf6", "#e8ecea", "#d0d9d6", "#a8b8b7", "#71868a"]),
    "trap": LinearSegmentedColormap.from_list("trap", ["#fbfaf6", "#f1e7de", "#dec9b9", "#c99680", "#96604f"]),
    "response": LinearSegmentedColormap.from_list("response", ["#fbfaf6", "#e8f1ed", "#c7ddd6", "#8bb9ac", "#477f78"]),
    "gain": LinearSegmentedColormap.from_list("gain", ["#fbfaf6", "#e8f1ed", "#c7ddd6", "#8bb9ac", "#477f78"]),
    "diverge": LinearSegmentedColormap.from_list("diverge", ["#6f8793", "#fbfaf6", "#b57462"]),
}

TYPOLOGY_COLORS = {
    "network access": "#557f78",
    "topography": "#71868a",
    "home charging": "#7a768f",
    "vulnerability": "#b57462",
    "mobility pressure": "#6f8793",
}


def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf.set_crs(WGS84, allow_override=True).to_crs(METRIC)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(METRIC)


def read_geo(path: Path) -> gpd.GeoDataFrame:
    if not path.exists() or path.stat().st_size < 100:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    gdf = gpd.read_file(path)
    gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf


def metric_bounds() -> tuple[float, float, float, float]:
    frame = gpd.GeoDataFrame(geometry=[gpd.GeoSeries.from_wkt(["POLYGON EMPTY"]).iloc[0]], crs=WGS84)
    frame = gpd.GeoDataFrame(geometry=[gpd.points_from_xy([BOUNDS_WGS[0], BOUNDS_WGS[2]], [BOUNDS_WGS[1], BOUNDS_WGS[3]])[0]], crs=WGS84)
    # Avoid relying on a polygon constructor in older Shapely builds.
    xs = [BOUNDS_WGS[0], BOUNDS_WGS[2]]
    ys = [BOUNDS_WGS[1], BOUNDS_WGS[3]]
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs, ys), crs=WGS84).to_crs(METRIC)
    minx, miny, maxx, maxy = pts.total_bounds
    return float(minx), float(miny), float(maxx), float(maxy)


def subset(gdf: gpd.GeoDataFrame, bounds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    minx, miny, maxx, maxy = bounds
    local = to_metric(gdf)
    return local.cx[minx:maxx, miny:maxy].copy()


def minmax(values: pd.Series | np.ndarray) -> pd.Series:
    s = pd.Series(values, dtype=float)
    lo, hi = s.min(skipna=True), s.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or np.isclose(lo, hi):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def gini(values: pd.Series) -> float:
    x = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(x) == 0 or np.isclose(x.sum(), 0):
        return float("nan")
    x = np.sort(x)
    n = len(x)
    return float((2 * np.arange(1, n + 1) @ x) / (n * x.sum()) - (n + 1) / n)


def load_roads() -> gpd.GeoDataFrame:
    path = PROCESSED / "road_network.graphml"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    _, edges = ox.graph_to_gdfs(ox.load_graphml(path))
    edges = edges.reset_index(drop=True)
    if edges.crs is None:
        edges = edges.set_crs(WGS84)
    highway = edges.get("highway", pd.Series(index=edges.index, dtype="object")).astype(str)
    edges["major"] = highway.str.contains("motorway|trunk|primary|secondary", case=False, na=False)
    return edges.loc[edges["major"].fillna(False)].copy()


def nearest_euclidean_minutes(zones: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> pd.Series:
    zones_m = to_metric(zones)
    chargers_m = to_metric(chargers)
    points = zones_m.geometry.representative_point()
    if chargers_m.empty:
        return pd.Series(np.nan, index=zones.index)
    mins = [chargers_m.distance(point).min() / 1000.0 / DEFAULT_SPEED_KPH * 60.0 for point in points]
    return pd.Series(mins, index=zones.index, dtype=float)


def add_response_columns(zones: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    z = zones.copy()
    current_raw = z["transition_pressure"].fillna(0) * (1 - z["access_screen"].fillna(0))
    post_raw = z["transition_pressure"].fillna(0) * (1 - z["expanded_access_screen"].fillna(z["access_screen"]))
    z["current_disadvantage_raw"] = current_raw
    z["post_disadvantage_raw"] = post_raw
    z["post_disadvantage_screen"] = minmax(post_raw).to_numpy()
    z["proposal_reduction_screen"] = (current_raw - post_raw).clip(lower=0)
    z["proposal_reduction_relative"] = minmax(z["proposal_reduction_screen"]).to_numpy()
    z["straight_line_min"] = nearest_euclidean_minutes(z, chargers).to_numpy()
    z["network_penalty_min"] = (z["nearest_charger_min"] - z["straight_line_min"]).clip(lower=0)
    z["network_penalty_screen"] = minmax(z["network_penalty_min"]).to_numpy()
    z["low_access_screen"] = 1 - z["access_screen"].fillna(0)

    components = pd.DataFrame(
        {
            "network access": z["low_access_screen"].fillna(0),
            "topography": z["topography_burden_screen"].fillna(0),
            "home charging": z["home_constraint_screen"].fillna(0),
            "vulnerability": z["vulnerability_screen"].fillna(0),
            "mobility pressure": z["mobility_pressure"].fillna(0),
        },
        index=z.index,
    )
    z["binding_constraint"] = components.idxmax(axis=1)
    z["binding_strength"] = components.max(axis=1)
    return z


def set_map(ax: plt.Axes, bounds: tuple[float, float, float, float]) -> None:
    minx, miny, maxx, maxy = bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_facecolor(BASE["canvas"])


def plot_base(ax: plt.Axes, zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, bounds: tuple[float, float, float, float]) -> None:
    local = subset(zones, bounds)
    if not local.empty:
        local.plot(ax=ax, facecolor=BASE["polygon"], edgecolor="#c7d0d8", linewidth=0.28, zorder=1)
    local_roads = subset(roads, bounds)
    if not local_roads.empty:
        local_roads.plot(ax=ax, color="#ffffff", linewidth=0.82, alpha=0.55, zorder=3)
        local_roads.plot(ax=ax, color=BASE["road_major"], linewidth=0.42, alpha=0.62, zorder=4)


def plot_metric(
    fig: plt.Figure,
    ax: plt.Axes,
    zones: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    column: str,
    cmap,
    title: str,
    cbar_label: str,
    bounds: tuple[float, float, float, float],
    vmin: float = 0,
    vmax: float = 1,
) -> None:
    set_map(ax, bounds)
    plot_base(ax, zones, roads, bounds)
    local = subset(zones, bounds)
    if local.empty:
        return
    miss = local[column].isna()
    if miss.any():
        local.loc[miss].plot(ax=ax, facecolor="#e8ecef", edgecolor="#c7d0d8", linewidth=0.25, hatch="///", zorder=2)
    local.loc[~miss].plot(
        ax=ax,
        column=column,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        edgecolor="white",
        linewidth=0.34,
        zorder=5,
    )
    ax.set_title(title, loc="left", pad=4)
    sm = ScalarMappable(norm=Normalize(vmin=vmin, vmax=vmax), cmap=cmap)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.034, pad=0.010)
    cb.set_label(cbar_label, fontsize=7.0)
    cb.ax.tick_params(labelsize=6.6, length=2)
    cb.outline.set_linewidth(0.35)


def plot_chargers(ax: plt.Axes, chargers: gpd.GeoDataFrame, bounds: tuple[float, float, float, float], size: int = 34) -> None:
    local = subset(chargers, bounds)
    if local.empty:
        return
    styles = {
        "CargaME": (BASE["cargame"], "o"),
        "EPM": (BASE["epm"], "s"),
        "OSM": (BASE["osm"], "^"),
    }
    for src, group in local.groupby("source"):
        color, marker = styles.get(src, ("#444444", "o"))
        group.plot(ax=ax, marker=marker, color=color, markersize=size, edgecolor="white", linewidth=0.45, zorder=10)


def feature_matrix(zones: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> None:
    bounds = metric_bounds()
    transit_lines = read_geo(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson")
    centralities = read_geo(RAW / "planning" / "geomedellin" / "centralities.geojson")
    z = zones.copy()
    z["nearest_time_screen"] = minmax(z["nearest_charger_min"]).to_numpy()
    z["slope_screen"] = minmax(z["slope_mean_pct"]).to_numpy()
    z["poverty_screen"] = z["vulnerability_screen"].fillna(0)

    fig, ax = plt.subplots(figsize=(7.15, 7.05), facecolor=BASE["page"])
    fig.subplots_adjust(left=0.025, right=0.985, top=0.985, bottom=0.155)
    fig.patch.set_facecolor(BASE["page"])

    set_map(ax, bounds)
    plot_base(ax, z, roads, bounds)
    local = subset(z, bounds)
    local.plot(
        ax=ax,
        column="disadvantage_screen",
        cmap=CMAPS["trap"],
        vmin=0,
        vmax=1,
        edgecolor="#fffdf8",
        linewidth=0.35,
        zorder=5,
    )
    cent = subset(centralities, bounds)
    if not cent.empty:
        cent.boundary.plot(ax=ax, color="#6c907f", linewidth=0.65, alpha=0.65, zorder=7)
    lines = subset(transit_lines, bounds)
    if not lines.empty:
        lines.plot(ax=ax, color=BASE["sitva"], linewidth=1.50, alpha=0.90, zorder=8)
    plot_chargers(ax, chargers, bounds, size=34)

    trap_cut = z["disadvantage_screen"].quantile(0.75)
    top = subset(z[z["disadvantage_screen"] >= trap_cut], bounds)
    if not top.empty:
        top.boundary.plot(ax=ax, color="#303a3e", linewidth=0.72, zorder=10)

    sm = ScalarMappable(norm=Normalize(vmin=0, vmax=1), cmap=CMAPS["trap"])
    sm.set_array([])
    cax = fig.add_axes([0.205, 0.086, 0.590, 0.018])
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=6.6, length=0)
    cb.set_label("baseline readiness-trap score", fontsize=7.2)

    fig.legend(
        handles=[
            Line2D([0], [0], color=BASE["sitva"], lw=1.8, label="SITVA/Metro lines"),
            Line2D([0], [0], color="#6c907f", lw=0.9, label="Centrality boundary"),
            Patch(facecolor="none", edgecolor="#303a3e", linewidth=0.9, label="Top trap quartile"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=BASE["cargame"], markersize=5, label="CargaME"),
            Line2D([0], [0], marker="s", color="w", markerfacecolor=BASE["epm"], markersize=5, label="EPM"),
            Line2D([0], [0], marker="^", color="w", markerfacecolor=BASE["osm"], markersize=5, label="OSM"),
        ],
        loc="lower center",
        ncol=6,
        frameon=False,
        bbox_to_anchor=(0.500, 0.026),
        fontsize=6.0,
        columnspacing=0.85,
        handlelength=1.35,
        handletextpad=0.35,
    )

    out = FIGURES / "fig_cities01_feature_matrix.png"
    fig.savefig(out, bbox_inches="tight", facecolor=BASE["page"])
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}")


def response_matrix(zones: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame) -> None:
    z = zones.copy()
    combined = pd.concat([z["current_disadvantage_raw"], z["post_disadvantage_raw"]]).astype(float)
    lo, hi = combined.min(skipna=True), combined.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or np.isclose(lo, hi):
        z["before_common"] = z["disadvantage_screen"].fillna(0)
        z["after_common"] = z["post_disadvantage_screen"].fillna(0)
    else:
        z["before_common"] = (z["current_disadvantage_raw"] - lo) / (hi - lo)
        z["after_common"] = (z["post_disadvantage_raw"] - lo) / (hi - lo)
    z["response_common"] = (z["before_common"] - z["after_common"]).clip(lower=0)

    top = z.sort_values("disadvantage_screen", ascending=False).head(12).copy()
    top = top.sort_values("before_common", ascending=True)
    y = np.arange(len(top))

    fig, ax = plt.subplots(figsize=(7.55, 4.85), facecolor="white")
    fig.subplots_adjust(left=0.170, right=0.975, top=0.940, bottom=0.230)
    fig.patch.set_facecolor("white")

    ax.axvspan(0.66, 1.03, color="#f4e7ea", alpha=0.65, zorder=0)
    for i, (_, row) in enumerate(top.iterrows()):
        color = TYPOLOGY_COLORS.get(row["binding_constraint"], "#6b7280")
        movement = ax.annotate(
            "",
            xy=(row["after_common"], i),
            xytext=(row["before_common"], i),
            arrowprops={
                "arrowstyle": "-|>",
                "color": color,
                "alpha": 0.82,
                "lw": 1.45 + 2.9 * float(row["response_common"]),
                "mutation_scale": 9.4,
                "shrinkA": 0.0,
                "shrinkB": 0.0,
            },
            annotation_clip=False,
        )
        movement.arrow_patch.set_zorder(2)
        ax.scatter(row["before_common"], i, s=34, color="#7b3a51", edgecolor="white", linewidth=0.45, zorder=4)
        ax.scatter(row["after_common"], i, s=34, color="#08519c", edgecolor="white", linewidth=0.45, zorder=5)

    ax.set_yticks(y)
    ax.set_yticklabels([f"zone {int(r.zone_id)}" for _, r in top.iterrows()], fontsize=6.8)
    ax.set_xlim(0.0, 1.03)
    ax.set_ylim(-0.65, len(top) - 0.35)
    ax.set_xlabel("readiness-trap disadvantage, normalized on one before/after scale", labelpad=7)
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.grid(axis="x", color="#e3e8ee", linewidth=0.60)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=2.5, color="#9aa7b2")

    ax.text(0.665, len(top) - 0.02, "high inherited trap range", ha="left", va="bottom", fontsize=6.4, color="#8a4f5d")

    present_constraints = [name for name in TYPOLOGY_COLORS if name in set(top["binding_constraint"])]
    status_handles = [
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#7b3a51", markeredgecolor="white", markersize=5.0, label="baseline"),
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#08519c", markeredgecolor="white", markersize=5.0, label="after expansion"),
    ]
    constraint_handles = [
        Line2D([0], [0], color=TYPOLOGY_COLORS[name], lw=2.1, alpha=0.72, label=name.replace(" pressure", ""))
        for name in present_constraints
    ]
    status_legend = ax.legend(
        handles=status_handles,
        frameon=False,
        fontsize=6.2,
        loc="upper left",
        bbox_to_anchor=(0.000, -0.165),
        borderaxespad=0,
        handlelength=1.0,
        ncol=2,
        columnspacing=1.2,
    )
    ax.add_artist(status_legend)
    ax.legend(
        handles=constraint_handles,
        title="Dominant residual constraint",
        frameon=False,
        fontsize=6.0,
        title_fontsize=6.1,
        loc="upper right",
        bbox_to_anchor=(1.000, -0.155),
        borderaxespad=0,
        handlelength=1.45,
        ncol=3,
        columnspacing=1.0,
    )
    out = FIGURES / "fig_cities02_response_matrix.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}")


def operational_robustness(zones: gpd.GeoDataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.45), constrained_layout=True, gridspec_kw={"width_ratios": [1.15, 1.05, 1.20]})
    fig.patch.set_facecolor("white")

    epm_path = RAW / "chargers" / "epm_public_charging_use_2019_2025.csv"
    if epm_path.exists():
        df = pd.read_csv(epm_path)
        month = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
            "noviembre": 11, "diciembre": 12,
        }
        df["month"] = df["mes"].astype(str).str.lower().map(month)
        df["year"] = pd.to_numeric(df["a_o"], errors="coerce")
        df["total"] = pd.to_numeric(df["total"], errors="coerce")
        df = df.dropna(subset=["year", "month", "total"]).copy()
        df["date"] = pd.to_datetime(dict(year=df["year"].astype(int), month=df["month"].astype(int), day=1))
        annual = df.groupby(df["date"].dt.year)["total"].sum()
        axes[0].bar(annual.index.astype(str), annual.values, color=BASE["cargame"], width=0.72)
        axes[0].set_title("(a) EPM public-use evidence", loc="left")
        axes[0].set_ylabel("reported source units")
        axes[0].tick_params(axis="x", rotation=0)
        axes[0].grid(axis="y", color="#e3e8ee", lw=0.6)

    reduction = zones["proposal_reduction_screen"].fillna(0)
    bins = pd.qcut(zones["disadvantage_screen"].rank(method="first"), 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"])
    q = pd.DataFrame({"quartile": bins, "reduction": reduction}).groupby("quartile", observed=True)["reduction"].mean()
    axes[1].bar(q.index.astype(str), q.values, color="#2f855a", width=0.72)
    axes[1].set_title("(b) proposal response by disadvantage", loc="left")
    axes[1].set_ylabel("mean reduction screen")
    axes[1].grid(axis="y", color="#e3e8ee", lw=0.6)

    rob_path = TABLES / "table_cities_robustness_summary.csv"
    if rob_path.exists():
        rob = pd.read_csv(rob_path)
        rob = rob.loc[rob["scenario"] != "base"].copy()
        rob["label"] = rob["scenario"].str.replace("_", " ", regex=False)
        rob = rob.sort_values("top10_jaccard")
        y = np.arange(len(rob))
        axes[2].scatter(rob["top10_jaccard"], y, color=BASE["epm"], s=28, label="top-10 overlap")
        axes[2].scatter(rob["access_gini"], y, color=BASE["cargame"], s=28, label="access Gini")
        axes[2].set_yticks(y)
        axes[2].set_yticklabels(rob["label"], fontsize=6.6)
        axes[2].set_xlim(0, 1.05)
        axes[2].set_title("(c) robustness narrows the claim", loc="left")
        axes[2].legend(frameon=False, loc="lower right", fontsize=6.6)
        axes[2].grid(axis="x", color="#e3e8ee", lw=0.6)

    for ax in axes:
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
    fig.suptitle("Operational evidence and robustness: active service, limited reliability, stable but not universal geography", fontsize=12.2, y=1.05)
    out = FIGURES / "fig_cities03_evidence_robustness.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}")


def write_story_tables(zones: gpd.GeoDataFrame) -> None:
    metrics = {
        "mean_nearest_network_min": zones["nearest_charger_min"].mean(),
        "max_nearest_network_min": zones["nearest_charger_min"].max(),
        "mean_network_penalty_min": zones["network_penalty_min"].mean(),
        "access_gini": gini(zones["access_screen"]),
        "mean_current_disadvantage_raw": zones["current_disadvantage_raw"].mean(),
        "mean_post_proposal_disadvantage_raw": zones["post_disadvantage_raw"].mean(),
        "mean_proposal_reduction": zones["proposal_reduction_screen"].mean(),
        "top_quartile_mean_proposal_reduction": zones.loc[zones["disadvantage_screen"] >= zones["disadvantage_screen"].quantile(0.75), "proposal_reduction_screen"].mean(),
        "max_proposal_reduction": zones["proposal_reduction_screen"].max(),
    }
    pd.DataFrame([metrics]).to_csv(TABLES / "table_cities_story_metrics.csv", index=False)

    counts = zones["binding_constraint"].value_counts().rename_axis("binding_constraint").reset_index(name="zone_count")
    counts.to_csv(TABLES / "table_cities_binding_constraints.csv", index=False)

    top = zones.sort_values("disadvantage_screen", ascending=False).head(8)
    top[
        [
            "zone_id",
            "municipality",
            "nearest_charger_min",
            "network_penalty_min",
            "access_screen",
            "disadvantage_screen",
            "proposal_reduction_screen",
            "proposal_reduction_relative",
            "post_disadvantage_screen",
            "binding_constraint",
        ]
    ].to_csv(TABLES / "table_cities_priority_response.csv", index=False)


def update_manifest() -> None:
    rows = [
        {
            "file": "fig_cities01_feature_matrix.png",
            "role": "territorial-features",
            "figure": "fig_cities01_feature_matrix.png",
            "status": "generated",
            "description": "Single-map baseline readiness-trap geography with supply evidence, SITVA and centrality structure, and top-quartile trap outlines.",
        },
        {
            "file": "fig_cities02_response_matrix.png",
            "role": "readiness-response",
            "figure": "fig_cities02_response_matrix.png",
            "status": "generated",
            "description": "Single-scale before-and-after response plot for inherited trap zones, with residual bottleneck labels.",
        },
        {
            "file": "fig_cities03_evidence_robustness.png",
            "role": "evidence-robustness",
            "figure": "fig_cities03_evidence_robustness.png",
            "status": "generated",
            "description": "Operational EPM evidence, proposal response by disadvantage quartile and robustness diagnostics.",
        },
    ]
    manifest_path = TABLES / "figure_manifest.csv"
    new = pd.DataFrame(rows)
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        key = "file" if "file" in manifest.columns else "figure"
        manifest = manifest[~manifest[key].isin(new["file"])]
        manifest = pd.concat([manifest, new], ignore_index=True, sort=False)
    else:
        manifest = new
    manifest.to_csv(manifest_path, index=False)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    zones = read_geo(PROCESSED / "readiness_screen.gpkg")
    chargers = read_geo(PROCESSED / "mapped_charger_evidence.gpkg")
    candidates = read_geo(PROCESSED / "candidate_validation_leads.gpkg")
    roads = load_roads()
    zones = add_response_columns(zones, chargers)
    zones.to_file(PROCESSED / "readiness_story_screen.gpkg", driver="GPKG")
    feature_matrix(zones, chargers, roads)
    response_matrix(zones, chargers, roads, candidates)
    operational_robustness(zones)
    write_story_tables(zones)
    update_manifest()


if __name__ == "__main__":
    main()
