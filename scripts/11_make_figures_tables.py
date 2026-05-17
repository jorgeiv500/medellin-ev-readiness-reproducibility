from __future__ import annotations

import json
import unicodedata
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pyproj import Transformer
from shapely.geometry import LineString, Point, box

from aaca_utils import ROOT

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.titlesize": 9.5,
        "axes.labelsize": 8.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.2,
        "axes.linewidth": 0.6,
        "axes.edgecolor": "#1f2933",
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "figure.facecolor": "#ffffff",
    }
)


RAW = ROOT / "data_raw"
PROCESSED = ROOT / "data_processed"
FIGURES = ROOT / "outputs" / "figures"
MAPS = ROOT / "outputs" / "maps"
TABLES = ROOT / "outputs" / "tables"

WGS84 = "EPSG:4326"
METRIC = "EPSG:3116"
DEFAULT_SPEED_KPH = 28.0
BASE_DECAY_MIN = 12.0
SHORT_DECAY_MIN = 8.0
WIDE_DECAY_MIN = 16.0
# Analytical frame for the urban charging story. The full metropolitan frame is
# still shown as context in Figure 1A.
WGS_BOUNDS = (-75.68, 6.12, -75.45, 6.38)

BASE = {
    "page": "#ffffff",
    "canvas": "#eef2f3",
    "polygon": "#f6f7f8",
    "boundary": "#aeb8c2",
    "boundary_light": "#d2d8de",
    "road": "#b9c3cc",
    "road_major": "#66758a",
    "sitva": "#111827",
    "station": "#f3b43f",
    "centrality": "#cfe8d5",
    "cargame": "#006d77",
    "epm": "#e76f51",
    "osm": "#7b52ab",
    "fuel": "#8f4bb3",
    "parking": "#7c8a99",
    "safety": "#9d0208",
    "text": "#1f2933",
    "muted": "#6b7280",
}

CMAPS = {
    "access": LinearSegmentedColormap.from_list(
        "cities_access", ["#f2f7f5", "#b8d8cc", "#5ba69c", "#0b5d67"]
    ),
    "disadvantage": LinearSegmentedColormap.from_list(
        "cities_disadvantage", ["#f7f7f7", "#f6d6dd", "#e58ca1", "#67001f"]
    ),
    "vulnerability": LinearSegmentedColormap.from_list(
        "cities_vulnerability", ["#f7f7f7", "#d9d9d9", "#969696", "#525252"]
    ),
    "improvement": LinearSegmentedColormap.from_list(
        "cities_improvement", ["#f7fbff", "#c6dbef", "#6baed6", "#08519c"]
    ),
}


def ensure_dirs() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)


def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf.set_crs(WGS84, allow_override=True).to_crs(METRIC) if gdf.crs is None else gdf.to_crs(METRIC)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(METRIC)


def metric_bounds(bounds: tuple[float, float, float, float] = WGS_BOUNDS) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    b = gpd.GeoSeries([box(minx, miny, maxx, maxy)], crs=WGS84).to_crs(METRIC).total_bounds
    return tuple(float(v) for v in b)


def clip_bbox(gdf: gpd.GeoDataFrame, bounds: tuple[float, float, float, float] = WGS_BOUNDS) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    gdf = gdf.to_crs(WGS84)
    minx, miny, maxx, maxy = bounds
    return gdf.cx[minx:maxx, miny:maxy].copy()


def subset_metric(gdf: gpd.GeoDataFrame, bounds_m: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    local = to_metric(gdf)
    minx, miny, maxx, maxy = bounds_m
    return local.cx[minx:maxx, miny:maxy].copy()


def read_amva_zones() -> gpd.GeoDataFrame:
    extracted = PROCESSED / "_amva_boundaries"
    shp_paths = list(extracted.rglob("*.shp")) if extracted.exists() else []
    if not shp_paths:
        zip_path = RAW / "boundaries" / "amva" / "zonificacion_macrozona_zonas_sit_shp.zip"
        if zip_path.exists():
            extracted.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extracted)
            shp_paths = list(extracted.rglob("*.shp"))
    zone_path = next((p for p in shp_paths if "ZONAS" in p.name.upper()), None)
    if zone_path is None and shp_paths:
        zone_path = shp_paths[0]
    if zone_path is None:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    zones = gpd.read_file(zone_path)
    zones = zones.loc[zones.geometry.notna() & ~zones.geometry.is_empty].copy()
    if zones.crs is None:
        zones = zones.set_crs(WGS84)
    return clip_bbox(zones)


def read_safe_geojson(path: Path) -> gpd.GeoDataFrame:
    if not path.exists() or path.stat().st_size < 100:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    gdf = gpd.read_file(path)
    gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return clip_bbox(gdf)


def read_roads() -> gpd.GeoDataFrame:
    path = PROCESSED / "road_network.graphml"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=WGS84)
    _, edges = ox.graph_to_gdfs(ox.load_graphml(path))
    edges = edges.reset_index(drop=True)
    if edges.crs is None:
        edges = edges.set_crs(WGS84)
    edges = clip_bbox(edges)
    edges["length_m"] = pd.to_numeric(edges.get("length"), errors="coerce").fillna(0)
    highway = edges.get("highway", pd.Series(index=edges.index, dtype="object")).astype(str)
    edges["major"] = highway.str.contains("motorway|trunk|primary|secondary", case=False, na=False)
    return edges


def read_graph():
    path = PROCESSED / "road_network.graphml"
    if not path.exists():
        return None
    try:
        return ox.load_graphml(path)
    except Exception as exc:
        print(f"Could not load road graph for network distances: {exc}")
        return None


def representative_points_wgs(gdf_metric: gpd.GeoDataFrame) -> gpd.GeoSeries:
    points_metric = gdf_metric.geometry.representative_point()
    return gpd.GeoSeries(points_metric, crs=gdf_metric.crs).to_crs(WGS84)


def graph_nodes_for_geometries(graph, geoms_wgs: gpd.GeoSeries) -> list[int]:
    if graph is None or geoms_wgs.empty:
        return []
    return list(ox.distance.nearest_nodes(graph, X=geoms_wgs.x.to_numpy(), Y=geoms_wgs.y.to_numpy()))


def network_cost_matrix(
    graph,
    origin_nodes: list[int],
    destination_nodes: list[int],
    weight: str = "length",
    cutoff: float | None = None,
) -> np.ndarray:
    if graph is None or not origin_nodes or not destination_nodes:
        return np.empty((len(origin_nodes), len(destination_nodes)))
    matrix = np.full((len(origin_nodes), len(destination_nodes)), np.nan, dtype=float)
    for i, origin in enumerate(origin_nodes):
        costs = nx.single_source_dijkstra_path_length(graph, origin, cutoff=cutoff, weight=weight)
        matrix[i, :] = [costs.get(dest, np.nan) for dest in destination_nodes]
    return matrix


def distance_decay_access(costs: np.ndarray, weights: np.ndarray, decay: float = BASE_DECAY_MIN) -> np.ndarray:
    if costs.size == 0:
        return np.zeros(costs.shape[0] if costs.ndim else 0)
    valid = np.isfinite(costs)
    contributions = np.zeros_like(costs, dtype=float)
    contributions[valid] = np.exp(-costs[valid] / decay)
    return contributions @ weights


def nearest_distance_to_layer(points: gpd.GeoSeries, layer: gpd.GeoDataFrame) -> np.ndarray:
    if layer.empty:
        return np.full(len(points), np.inf)
    layer_m = to_metric(layer)
    return np.array([float(layer_m.distance(point).min()) for point in points], dtype=float)


def activity_anchor_scores(points: gpd.GeoSeries) -> np.ndarray:
    if points.empty:
        return np.array([], dtype=float)
    centralities = read_safe_geojson(RAW / "planning" / "geomedellin" / "centralities.geojson")
    stations = read_safe_geojson(RAW / "transport" / "geomedellin" / "mass_transport_stations.geojson")
    gtfs_stops = read_gtfs_stops()

    transit_dist = np.minimum(
        nearest_distance_to_layer(points, stations),
        nearest_distance_to_layer(points, gtfs_stops),
    )
    centrality_dist = nearest_distance_to_layer(points, centralities)
    transit_score = np.exp(-np.nan_to_num(transit_dist, nan=np.inf, posinf=np.inf) / 650.0)
    centrality_score = np.exp(-np.nan_to_num(centrality_dist, nan=np.inf, posinf=np.inf) / 900.0)
    score = 0.55 * transit_score + 0.45 * centrality_score
    return np.clip(score, 0, 1)


def parse_decimal(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def normalize_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.upper().split())


def minmax(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    lo = values.min(skipna=True)
    hi = values.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(np.zeros(len(values)), index=values.index, dtype=float)
    return (values - lo) / (hi - lo)


def gini(values: pd.Series | np.ndarray) -> float:
    arr = np.asarray(pd.to_numeric(pd.Series(values), errors="coerce").dropna(), dtype=float)
    if len(arr) == 0:
        return float("nan")
    arr = np.clip(arr, 0, None)
    if np.all(arr == 0):
        return 0.0
    arr = np.sort(arr)
    n = len(arr)
    return float((2 * np.sum((np.arange(1, n + 1) * arr)) / (n * np.sum(arr))) - (n + 1) / n)


def lorenz_xy(values: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(pd.to_numeric(pd.Series(values), errors="coerce").dropna(), dtype=float)
    arr = np.sort(np.clip(arr, 0, None))
    if len(arr) == 0 or arr.sum() == 0:
        return np.array([0, 1]), np.array([0, 1])
    cum = np.insert(np.cumsum(arr) / arr.sum(), 0, 0)
    pop = np.linspace(0, 1, len(cum))
    return pop, cum


def read_cargame_chargers() -> gpd.GeoDataFrame:
    path = RAW / "chargers" / "cargame_valle_aburra.geojson"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["source", "name", "operator", "power_kw", "geometry"], geometry="geometry", crs=WGS84)
    gdf = gpd.read_file(path).to_crs(WGS84)
    gdf["source"] = "CargaME"
    gdf["name"] = gdf.get("Nombre", pd.Series(index=gdf.index, dtype="object")).fillna("CargaME station")
    gdf["operator"] = gdf.get("Operador", pd.Series(index=gdf.index, dtype="object")).astype(str)
    gdf["power_kw"] = pd.to_numeric(gdf.get("PotenciaMax"), errors="coerce")
    return clip_bbox(gdf[["source", "name", "operator", "power_kw", "geometry"]])


def read_epm_chargers() -> gpd.GeoDataFrame:
    path = RAW / "chargers" / "epm_gnv_ev_stations.csv"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["source", "name", "operator", "power_kw", "geometry"], geometry="geometry", crs=WGS84)
    df = pd.read_csv(path)
    if "tipo_de_estacion" in df.columns:
        df = df.loc[df["tipo_de_estacion"].astype(str).str.contains("electrica|eléctrica|elÃ©ctrica", case=False, na=False)].copy()
    df["lat"] = parse_decimal(df.get("latitud", pd.Series(dtype="object")))
    df["lon"] = parse_decimal(df.get("longitud", pd.Series(dtype="object")))
    df.loc[df["lon"] > 0, "lon"] = -df.loc[df["lon"] > 0, "lon"]
    df = df.dropna(subset=["lat", "lon"])
    df = df.loc[df["lat"].between(5.5, 7.0) & df["lon"].between(-77.0, -74.5)].copy()
    df = df.drop_duplicates(subset=["estaci_n", "lat", "lon"])
    df["power_kw"] = pd.to_numeric(
        df.get("est_ndar_cargador", pd.Series(dtype="object"))
        .astype(str)
        .str.extract(r"(\d+(?:[,.]\d+)?)", expand=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )
    gdf = gpd.GeoDataFrame(
        {
            "source": "EPM",
            "name": df.get("estaci_n", pd.Series(index=df.index, dtype="object")).fillna("EPM station"),
            "operator": "EPM",
            "power_kw": df["power_kw"],
        },
        geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs=WGS84,
    )
    return clip_bbox(gdf)


def osm_points(path: Path, source: str, default_name: str) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame(columns=["source", "name", "operator", "geometry"], geometry="geometry", crs=WGS84)
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for element in data.get("elements", []):
        tags = element.get("tags") or {}
        lon = element.get("lon")
        lat = element.get("lat")
        if lon is None or lat is None:
            center = element.get("center") or {}
            lon = center.get("lon")
            lat = center.get("lat")
        if lon is None or lat is None:
            continue
        rows.append(
            {
                "source": source,
                "name": tags.get("name") or tags.get("brand") or default_name,
                "operator": tags.get("operator") or tags.get("brand") or "",
                "geometry": Point(float(lon), float(lat)),
            }
        )
    return clip_bbox(gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84))


def read_chargers() -> gpd.GeoDataFrame:
    chargers = pd.concat(
        [
            read_cargame_chargers(),
            read_epm_chargers(),
            osm_points(RAW / "osm" / "overpass_charging_stations.json", "OSM", "OSM charger"),
        ],
        ignore_index=True,
    )
    if chargers.empty:
        return gpd.GeoDataFrame(columns=["source", "name", "operator", "power_kw", "geometry"], geometry="geometry", crs=WGS84)
    return gpd.GeoDataFrame(chargers, geometry="geometry", crs=WGS84)


def read_vulnerability() -> gpd.GeoDataFrame:
    poverty = read_safe_geojson(RAW / "demographics" / "medellin_arcgis" / "ecv_multidimensional_poverty.geojson")
    imcv = read_safe_geojson(RAW / "demographics" / "medellin_arcgis" / "ecv_imcv.geojson")
    if poverty.empty:
        return gpd.GeoDataFrame(columns=["poverty_2024", "imcv_2024", "geometry"], geometry="geometry", crs=WGS84)
    keep = poverty[["nombre", "i_2024", "geometry"]].rename(columns={"i_2024": "poverty_2024"}).copy()
    if not imcv.empty:
        keep = keep.merge(
            imcv.drop(columns="geometry")[["nombre", "i_2024"]].rename(columns={"i_2024": "imcv_2024"}),
            on="nombre",
            how="left",
        )
    return clip_bbox(keep)


def read_trip_origin_by_municipality() -> pd.Series:
    path = RAW / "mobility" / "eod_valle_aburra" / "EOD_2017_DatosViajes_1_0.csv"
    if not path.exists():
        return pd.Series(dtype=float)
    mode_cols = [
        "DESC_MODO_TTE_E1",
        "DESC_MODO_TTE_E2",
        "DESC_MODO_TTE_E3",
        "DESC_MODO_TTE_E4",
        "DEC_MODO_TTE_E5",
        "DESC_MODO_TTE_E6",
        "DESC_MODO_TTE_E7",
    ]
    trips = pd.read_csv(path, sep=";", encoding="latin-1", usecols=["MUNICIPIO_O", *mode_cols])
    trips["municipality_key"] = trips["MUNICIPIO_O"].map(normalize_name)
    mode_text = trips[mode_cols].fillna("").astype(str).agg(" ".join, axis=1)
    private_motorized = mode_text.str.contains(
        "Auto Particular|Moto|Taxi|Particular con pago|Motocarro",
        case=False,
        regex=True,
        na=False,
    )
    trips = trips.loc[private_motorized].copy()
    return trips["municipality_key"].value_counts().astype(float)


def read_home_constraint_by_municipality() -> pd.Series:
    path = RAW / "mobility" / "eod_valle_aburra" / "EOD_2017_DatosHogares.csv"
    if not path.exists():
        return pd.Series(dtype=float)
    households = pd.read_csv(path, sep=";", encoding="latin-1", usecols=["NOM_MUNICIPIO", "#CELDAS_PARQUEO"])
    households["municipality_key"] = households["NOM_MUNICIPIO"].map(normalize_name)
    cells = pd.to_numeric(households["#CELDAS_PARQUEO"], errors="coerce").fillna(0)
    households["home_charging_constraint"] = (cells <= 0).astype(float)
    return households.groupby("municipality_key")["home_charging_constraint"].mean()


def read_fuel_candidates() -> gpd.GeoDataFrame:
    return osm_points(RAW / "osm" / "overpass_fuel_stations.json", "OSM fuel", "Fuel station candidate")


def read_parking_candidates() -> gpd.GeoDataFrame:
    return osm_points(RAW / "osm" / "overpass_parking.json", "OSM parking", "Parking candidate")


def candidate_pool(chargers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pool = pd.concat([read_fuel_candidates(), read_parking_candidates()], ignore_index=True)
    if pool.empty:
        return gpd.GeoDataFrame(columns=["source", "name", "geometry"], geometry="geometry", crs=WGS84)
    pool = gpd.GeoDataFrame(pool, geometry="geometry", crs=WGS84)
    pool_m = to_metric(pool).copy()
    if not chargers.empty:
        chargers_m = to_metric(chargers)
        nearest = pool_m.geometry.apply(lambda geom: chargers_m.distance(geom).min())
        pool_m = pool_m.loc[nearest >= 300].copy()
    return pool_m.to_crs(WGS84)


def read_gtfs_shapes() -> gpd.GeoDataFrame:
    path = RAW / "gtfs" / "metro_medellin" / "shapes.txt"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["shape_id", "geometry"], geometry="geometry", crs=WGS84)
    df = pd.read_csv(path)
    lines = []
    for shape_id, group in df.sort_values("shape_pt_sequence").groupby("shape_id"):
        coords = list(zip(group["shape_pt_lon"], group["shape_pt_lat"]))
        if len(coords) >= 2:
            lines.append({"shape_id": shape_id, "geometry": LineString(coords)})
    return clip_bbox(gpd.GeoDataFrame(lines, geometry="geometry", crs=WGS84))


def read_gtfs_stops() -> gpd.GeoDataFrame:
    path = RAW / "gtfs" / "metro_medellin" / "stops.txt"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["stop_name", "geometry"], geometry="geometry", crs=WGS84)
    df = pd.read_csv(path)
    df = df.dropna(subset=["stop_lon", "stop_lat"])
    gdf = gpd.GeoDataFrame(
        df[["stop_id", "stop_name", "location_type"]],
        geometry=[Point(xy) for xy in zip(df["stop_lon"], df["stop_lat"])],
        crs=WGS84,
    )
    return clip_bbox(gdf)


def read_hgt_subset(bounds: tuple[float, float, float, float] = WGS_BOUNDS, max_pixels: int = 900) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    minx, miny, maxx, maxy = bounds
    tile_lat = int(np.floor(maxy))
    tile_lon = int(np.floor(minx))
    path = RAW / "topography" / f"N{tile_lat:02d}W{abs(tile_lon):03d}.hgt"
    if not path.exists():
        return np.empty((0, 0)), bounds
    size = int(round(np.sqrt(path.stat().st_size / 2)))
    arr = np.fromfile(path, dtype=">i2").reshape((size, size)).astype(float)
    arr[arr <= -32000] = np.nan
    north = tile_lat + 1
    west = tile_lon
    rows = np.arange(size)
    cols = np.arange(size)
    lats = north - rows / (size - 1)
    lons = west + cols / (size - 1)
    row_mask = (lats >= miny) & (lats <= maxy)
    col_mask = (lons >= minx) & (lons <= maxx)
    subset = arr[np.ix_(row_mask, col_mask)]
    sub_lats = lats[row_mask]
    sub_lons = lons[col_mask]
    if subset.size == 0:
        return np.empty((0, 0)), bounds
    step = max(1, int(max(subset.shape) / max_pixels))
    subset = subset[::step, ::step]
    extent_wgs = (float(sub_lons.min()), float(sub_lons.max()), float(sub_lats.min()), float(sub_lats.max()))
    return subset, extent_wgs


def metric_extent(extent_wgs: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    minx, maxx, miny, maxy = extent_wgs
    transformer = Transformer.from_crs(WGS84, METRIC, always_xy=True)
    x0, y0 = transformer.transform(minx, miny)
    x1, y1 = transformer.transform(maxx, maxy)
    return min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)


def dem_surface(bounds: tuple[float, float, float, float] = WGS_BOUNDS) -> tuple[np.ndarray, np.ndarray, tuple[float, float, float, float]]:
    elev, extent = read_hgt_subset(bounds, max_pixels=1800)
    if elev.size == 0:
        return elev, np.empty((0, 0)), extent
    minlon, maxlon, minlat, maxlat = extent
    rows, cols = elev.shape
    lat_span = max(maxlat - minlat, 1e-9)
    lon_span = max(maxlon - minlon, 1e-9)
    dy = 111_320.0 * lat_span / max(rows - 1, 1)
    dx = 111_320.0 * np.cos(np.deg2rad((minlat + maxlat) / 2)) * lon_span / max(cols - 1, 1)
    gy, gx = np.gradient(elev, dy, dx)
    slope_pct = np.sqrt(gx**2 + gy**2) * 100
    return elev, slope_pct, extent


def sample_surface(values: np.ndarray, extent_wgs: tuple[float, float, float, float], geoms_wgs: gpd.GeoSeries) -> np.ndarray:
    if values.size == 0 or geoms_wgs.empty:
        return np.full(len(geoms_wgs), np.nan)
    minlon, maxlon, minlat, maxlat = extent_wgs
    rows, cols = values.shape
    out = []
    for geom in geoms_wgs:
        if geom.is_empty:
            out.append(np.nan)
            continue
        lon, lat = geom.x, geom.y
        if lon < minlon or lon > maxlon or lat < minlat or lat > maxlat:
            out.append(np.nan)
            continue
        col = int(round((lon - minlon) / max(maxlon - minlon, 1e-9) * (cols - 1)))
        row = int(round((maxlat - lat) / max(maxlat - minlat, 1e-9) * (rows - 1)))
        row = int(np.clip(row, 0, rows - 1))
        col = int(np.clip(col, 0, cols - 1))
        out.append(float(values[row, col]))
    return np.asarray(out, dtype=float)


def sample_points_in_polygon(poly, step_m: float = 900.0, max_points: int = 180) -> list[Point]:
    if poly.is_empty:
        return []
    minx, miny, maxx, maxy = poly.bounds
    xs = np.arange(minx, maxx + step_m, step_m)
    ys = np.arange(miny, maxy + step_m, step_m)
    points = []
    for x in xs:
        for y in ys:
            p = Point(float(x), float(y))
            if poly.contains(p):
                points.append(p)
                if len(points) >= max_points:
                    return points
    if not points:
        points = [poly.representative_point()]
    return points


def zone_topography_metrics(zones_m: gpd.GeoDataFrame) -> pd.DataFrame:
    elev, slope_pct, extent = dem_surface()
    rows = []
    for idx, geom in zones_m.geometry.items():
        samples_m = sample_points_in_polygon(geom)
        samples_wgs = gpd.GeoSeries(samples_m, crs=METRIC).to_crs(WGS84)
        elev_values = sample_surface(elev, extent, samples_wgs)
        slope_values = sample_surface(slope_pct, extent, samples_wgs)
        rows.append(
            {
                "index": idx,
                "elevation_mean_m": float(np.nanmean(elev_values)) if np.isfinite(elev_values).any() else np.nan,
                "slope_mean_pct": float(np.nanmean(slope_values)) if np.isfinite(slope_values).any() else np.nan,
                "slope_p75_pct": float(np.nanpercentile(slope_values, 75)) if np.isfinite(slope_values).any() else np.nan,
            }
        )
    topo = pd.DataFrame(rows).set_index("index")
    topo["topography_burden_screen"] = minmax(
        0.70 * topo["slope_mean_pct"].fillna(topo["slope_mean_pct"].median())
        + 0.30 * topo["elevation_mean_m"].fillna(topo["elevation_mean_m"].median())
    )
    return topo


def build_readiness_screen(zones: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    zones_m = to_metric(zones).copy()
    zones_m["zone_id"] = np.arange(len(zones_m))
    mun_col = next((c for c in zones_m.columns if c.upper() == "MUNICIPIO"), None)
    if mun_col is None:
        zones_m["municipality"] = "Unknown"
    else:
        zones_m["municipality"] = zones_m[mun_col].astype(str)
    zones_m["municipality_key"] = zones_m["municipality"].map(normalize_name)

    points = zones_m.geometry.representative_point()
    chargers_m = to_metric(chargers)
    reliability = {"CargaME": 1.0, "EPM": 0.95, "OSM": 0.65}
    cost_matrix = np.empty((len(zones_m), 0))
    length_matrix = np.empty((len(zones_m), 0))
    euclidean_dist = np.empty((len(zones_m), 0))
    euclidean_time = np.empty((len(zones_m), 0))
    weights = np.array([], dtype=float)
    charger_anchor = np.array([], dtype=float)
    access_variants: dict[str, np.ndarray] = {}
    graph = read_graph()
    if chargers_m.empty:
        zones_m["nearest_charger_km"] = np.nan
        zones_m["nearest_charger_min"] = np.nan
        zones_m["distance_method"] = "no_chargers"
        zones_m["access_raw"] = 0.0
        zones_m["access_screen"] = 0.0
    else:
        charger_anchor = activity_anchor_scores(chargers_m.geometry)
        chargers_m["activity_anchor_score"] = charger_anchor
        weights = (
            chargers_m["source"].map(reliability).fillna(0.5).to_numpy()
            * (0.45 + 0.90 * charger_anchor)
        )
        zone_nodes = graph_nodes_for_geometries(graph, representative_points_wgs(zones_m))
        charger_nodes = graph_nodes_for_geometries(graph, to_metric(chargers).to_crs(WGS84).geometry)
        network_time_s = network_cost_matrix(graph, zone_nodes, charger_nodes, weight="travel_time", cutoff=4 * 60 * 60)
        network_dist = network_cost_matrix(graph, zone_nodes, charger_nodes, weight="length", cutoff=120000)
        euclidean_dist = np.vstack([chargers_m.geometry.distance(pt).to_numpy() for pt in points])
        euclidean_time = euclidean_dist / 1000.0 / DEFAULT_SPEED_KPH * 60.0
        if network_time_s.shape == (len(zones_m), len(chargers_m)) and np.isfinite(network_time_s).any():
            cost_matrix = network_time_s / 60.0
            length_matrix = network_dist if network_dist.shape == cost_matrix.shape and np.isfinite(network_dist).any() else euclidean_dist
            zones_m["distance_method"] = "osm_drive_network_travel_time"
        else:
            cost_matrix = euclidean_time
            length_matrix = euclidean_dist
            zones_m["distance_method"] = "euclidean_time_fallback"
        zones_m["nearest_charger_min"] = np.nanmin(cost_matrix, axis=1)
        zones_m["nearest_charger_km"] = np.nanmin(length_matrix, axis=1) / 1000
        zones_m["access_raw"] = distance_decay_access(cost_matrix, weights, decay=BASE_DECAY_MIN)
        zones_m["access_screen"] = minmax(zones_m["access_raw"]).fillna(0)
        access_variants["base"] = zones_m["access_screen"].to_numpy(dtype=float)
        no_anchor_weights = chargers_m["source"].map(reliability).fillna(0.5).to_numpy()
        access_variants["no_activity_anchors"] = minmax(
            pd.Series(distance_decay_access(cost_matrix, no_anchor_weights, decay=BASE_DECAY_MIN), index=zones_m.index)
        ).fillna(0).to_numpy(dtype=float)
        access_variants["euclidean_distance"] = minmax(
            pd.Series(distance_decay_access(euclidean_time, weights, decay=BASE_DECAY_MIN), index=zones_m.index)
        ).fillna(0).to_numpy(dtype=float)
        strong_mask = chargers_m["source"].isin(["CargaME", "EPM"]).to_numpy()
        strong_weights = np.where(strong_mask, weights, 0.0)
        access_variants["cargame_epm_only"] = minmax(
            pd.Series(distance_decay_access(cost_matrix, strong_weights, decay=BASE_DECAY_MIN), index=zones_m.index)
        ).fillna(0).to_numpy(dtype=float)
        for decay in (SHORT_DECAY_MIN, WIDE_DECAY_MIN):
            access_variants[f"decay_{int(decay)}min"] = minmax(
                pd.Series(distance_decay_access(cost_matrix, weights, decay=decay), index=zones_m.index)
            ).fillna(0).to_numpy(dtype=float)

    topo = zone_topography_metrics(zones_m)
    for col in ["elevation_mean_m", "slope_mean_pct", "slope_p75_pct", "topography_burden_screen"]:
        zones_m[col] = topo[col]

    trips = read_trip_origin_by_municipality()
    zones_m["private_motorized_origins_municipality"] = zones_m["municipality_key"].map(trips).fillna(0)
    zones_m["mobility_pressure"] = minmax(zones_m["private_motorized_origins_municipality"]).fillna(0)

    home_constraint = read_home_constraint_by_municipality()
    zones_m["home_charging_constraint"] = zones_m["municipality_key"].map(home_constraint)
    zones_m["home_constraint_screen"] = minmax(zones_m["home_charging_constraint"]).fillna(0)

    vuln = read_vulnerability()
    zones_m["poverty_2024"] = np.nan
    zones_m["imcv_2024"] = np.nan
    if not vuln.empty:
        vuln_m = to_metric(vuln)
        point_gdf = gpd.GeoDataFrame(zones_m[["zone_id"]], geometry=points, crs=METRIC)
        joined = gpd.sjoin(
            point_gdf,
            vuln_m[["nombre", "poverty_2024", "imcv_2024", "geometry"]],
            predicate="within",
            how="left",
        )
        joined = joined.drop_duplicates("zone_id").set_index("zone_id")
        zones_m["poverty_2024"] = zones_m["zone_id"].map(joined["poverty_2024"])
        zones_m["imcv_2024"] = zones_m["zone_id"].map(joined["imcv_2024"])

    zones_m["vulnerability_screen"] = minmax(zones_m["poverty_2024"])
    vuln_fill = zones_m["vulnerability_screen"].fillna(0)
    zones_m["transition_pressure"] = minmax(
        0.40 * zones_m["mobility_pressure"].fillna(0)
        + 0.25 * zones_m["home_constraint_screen"].fillna(0)
        + 0.25 * vuln_fill
        + 0.10 * zones_m["topography_burden_screen"].fillna(0)
    )
    # Vulnerability is already part of transition_pressure. Keeping it out of
    # the final disadvantage multiplier avoids double counting the same social
    # condition in the baseline trap score.
    zones_m["disadvantage_screen"] = minmax(
        zones_m["transition_pressure"].fillna(0)
        * (1 - zones_m["access_screen"].fillna(0))
    )
    zones_m["low_access_high_vulnerability"] = (
        (zones_m["access_screen"] <= zones_m["access_screen"].median())
        & (zones_m["vulnerability_screen"] >= zones_m["vulnerability_screen"].median(skipna=True))
    )
    access_variants["topography_penalized_access"] = minmax(
        zones_m["access_screen"].fillna(0) * (1 - 0.25 * zones_m["topography_burden_screen"].fillna(0))
    ).fillna(0).to_numpy(dtype=float)

    selected = select_candidate_leads(zones_m, chargers, n=20, graph=graph)
    if not selected.empty:
        selected_m = to_metric(selected)
        zone_nodes = graph_nodes_for_geometries(graph, representative_points_wgs(zones_m))
        selected_nodes = graph_nodes_for_geometries(graph, selected_m.to_crs(WGS84).geometry)
        candidate_time_s = network_cost_matrix(graph, zone_nodes, selected_nodes, weight="travel_time", cutoff=4 * 60 * 60)
        if candidate_time_s.shape == (len(zones_m), len(selected_m)) and np.isfinite(candidate_time_s).any():
            candidate_cost = candidate_time_s / 60.0
        else:
            candidate_dist = np.vstack([selected_m.geometry.distance(pt).to_numpy() for pt in points])
            candidate_cost = candidate_dist / 1000.0 / DEFAULT_SPEED_KPH * 60.0
        candidate_weights = np.repeat(0.70, len(selected_m))
        candidate_access = distance_decay_access(candidate_cost, candidate_weights, decay=BASE_DECAY_MIN)
        expanded_access = zones_m["access_raw"].fillna(0).to_numpy() + candidate_access
        zones_m["expanded_access_screen"] = minmax(pd.Series(expanded_access, index=zones_m.index)).fillna(0)
        zones_m["candidate_gain_screen"] = (zones_m["expanded_access_screen"] - zones_m["access_screen"]).clip(lower=0)
    else:
        zones_m["expanded_access_screen"] = zones_m["access_screen"]
        zones_m["candidate_gain_screen"] = 0.0

    out = zones_m.to_crs(METRIC)
    out.to_file(PROCESSED / "readiness_screen.gpkg", driver="GPKG")
    if not selected.empty:
        to_metric(selected).to_file(PROCESSED / "candidate_validation_leads.gpkg", driver="GPKG")
    write_results_tables(out, selected, access_variants)
    return out, selected


def select_candidate_leads(zones_m: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame, n: int = 20, graph=None) -> gpd.GeoDataFrame:
    candidates = candidate_pool(chargers)
    if candidates.empty or zones_m.empty:
        return gpd.GeoDataFrame(columns=["score", "geometry"], geometry="geometry", crs=WGS84)
    cand_m = to_metric(candidates).copy()
    zone_points = zones_m.geometry.representative_point()
    weights = zones_m["disadvantage_screen"].fillna(0).to_numpy()
    zone_nodes = graph_nodes_for_geometries(graph, representative_points_wgs(zones_m))
    candidate_nodes = graph_nodes_for_geometries(graph, cand_m.to_crs(WGS84).geometry)
    network_time_s = network_cost_matrix(graph, zone_nodes, candidate_nodes, weight="travel_time", cutoff=4 * 60 * 60)
    if network_time_s.shape == (len(zones_m), len(cand_m)) and np.isfinite(network_time_s).any():
        cost = network_time_s / 60.0
        cand_m["candidate_impedance_method"] = "osm_drive_network_travel_time"
    else:
        dist = np.vstack([cand_m.geometry.distance(point).to_numpy() for point in zone_points])
        cost = dist / 1000.0 / DEFAULT_SPEED_KPH * 60.0
        cand_m["candidate_impedance_method"] = "euclidean_time_fallback"
    valid = np.isfinite(cost)
    contributions = np.zeros_like(cost, dtype=float)
    contributions[valid] = np.exp(-cost[valid] / WIDE_DECAY_MIN)
    scores = weights @ contributions
    cand_m["validation_score"] = scores
    cand_m["nearest_priority_zone_min"] = np.nanmin(cost, axis=0)
    cand_m = cand_m.sort_values("validation_score", ascending=False).head(n).copy()
    return cand_m.to_crs(WGS84)


def latex_escape(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def fmt_num(value: object, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "--"
    if not np.isfinite(number):
        return "--"
    return f"{number:.{digits}f}"


def jaccard_top(base: pd.Series, variant: pd.Series, n: int = 10) -> float:
    base_ids = set(base.sort_values(ascending=False).head(n).index)
    variant_ids = set(variant.sort_values(ascending=False).head(n).index)
    if not base_ids and not variant_ids:
        return float("nan")
    return len(base_ids & variant_ids) / len(base_ids | variant_ids)


def write_latex_table(path: Path, header: list[str], rows: list[list[str]], align: str) -> None:
    lines = [r"\begin{tabular}{" + align + "}", r"\toprule"]
    lines.append(" & ".join(header) + r" \\")
    lines.append(r"\midrule")
    for row in rows:
        lines.append(" & ".join(row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {path.relative_to(ROOT)}")


def write_priority_zone_table(zones: gpd.GeoDataFrame) -> None:
    cols = [
        "zone_id",
        "municipality",
        "access_screen",
        "nearest_charger_min",
        "nearest_charger_km",
        "slope_mean_pct",
        "home_charging_constraint",
        "poverty_2024",
        "disadvantage_screen",
    ]
    top = zones.sort_values("disadvantage_screen", ascending=False).head(8).copy()
    top[cols].to_csv(TABLES / "table_cities_priority_zones.csv", index=False)
    rows = []
    for _, row in top.iterrows():
        rows.append(
            [
                str(int(row["zone_id"])),
                latex_escape(row["municipality"]),
                fmt_num(row["access_screen"]),
                fmt_num(row["nearest_charger_min"], 1),
                fmt_num(row["nearest_charger_km"], 1),
                fmt_num(row["slope_mean_pct"], 1),
                fmt_num(row["home_charging_constraint"]),
                fmt_num(row["poverty_2024"], 1),
                fmt_num(row["disadvantage_screen"]),
            ]
        )
    write_latex_table(
        TABLES / "table_cities_priority_zones.tex",
        ["Zone", "Municipality", "Access", "Nearest min", "Nearest km", "Slope \\%", "Home constraint", "Poverty \\%", "Disadv."],
        rows,
        "rlrrrrrrr",
    )


def write_access_extremes_table(zones: gpd.GeoDataFrame) -> None:
    low = zones.sort_values("access_screen", ascending=True).head(5).assign(group="Lowest access")
    high = zones.sort_values("access_screen", ascending=False).head(5).assign(group="Highest access")
    combined = pd.concat([low, high], ignore_index=True)
    combined[["group", "zone_id", "municipality", "access_screen", "nearest_charger_min", "nearest_charger_km", "slope_mean_pct", "disadvantage_screen"]].to_csv(
        TABLES / "table_cities_access_extremes.csv", index=False
    )
    rows = []
    for _, row in combined.iterrows():
        rows.append(
            [
                latex_escape(row["group"]),
                str(int(row["zone_id"])),
                latex_escape(row["municipality"]),
                fmt_num(row["access_screen"]),
                fmt_num(row["nearest_charger_min"], 1),
                fmt_num(row["nearest_charger_km"], 1),
                fmt_num(row["slope_mean_pct"], 1),
                fmt_num(row["disadvantage_screen"]),
            ]
        )
    write_latex_table(
        TABLES / "table_cities_access_extremes.tex",
        ["Group", "Zone", "Municipality", "Access", "Nearest min", "Nearest km", "Slope \\%", "Disadv."],
        rows,
        "lrlrrrrr",
    )


def write_robustness_summary(zones: gpd.GeoDataFrame, access_variants: dict[str, np.ndarray]) -> pd.DataFrame:
    vuln = zones["vulnerability_screen"].fillna(0)
    base_transition = zones["transition_pressure"].fillna(0)
    base_disadv = zones["disadvantage_screen"].fillna(0)
    scenarios = {
        "base": ("Base network, source, activity, vulnerability and topography screen", base_transition, zones["access_screen"].fillna(0)),
        "no_activity_anchors": ("Removes SITVA/centrality activity anchoring from access", base_transition, pd.Series(access_variants.get("no_activity_anchors", zones["access_screen"]), index=zones.index)),
        "euclidean_distance": ("Uses straight-line rather than OSM network impedance", base_transition, pd.Series(access_variants.get("euclidean_distance", zones["access_screen"]), index=zones.index)),
        "cargame_epm_only": ("Keeps stronger CargaME/EPM evidence and removes OSM supply", base_transition, pd.Series(access_variants.get("cargame_epm_only", zones["access_screen"]), index=zones.index)),
        "short_decay_8min": ("Shorter destination-charging reach threshold", base_transition, pd.Series(access_variants.get("decay_8min", zones["access_screen"]), index=zones.index)),
        "wide_decay_16min": ("Wider destination-charging reach threshold", base_transition, pd.Series(access_variants.get("decay_16min", zones["access_screen"]), index=zones.index)),
        "topography_penalized_access": ("Penalizes access in higher-slope/elevation zones", base_transition, pd.Series(access_variants.get("topography_penalized_access", zones["access_screen"]), index=zones.index)),
        "no_vulnerability": (
            "Removes social vulnerability from transition pressure",
            minmax(0.55 * zones["mobility_pressure"].fillna(0) + 0.30 * zones["home_constraint_screen"].fillna(0) + 0.15 * zones["topography_burden_screen"].fillna(0)),
            zones["access_screen"].fillna(0),
        ),
        "no_home_constraint": (
            "Removes residential parking constraint from transition pressure",
            minmax(0.50 * zones["mobility_pressure"].fillna(0) + 0.35 * vuln + 0.15 * zones["topography_burden_screen"].fillna(0)),
            zones["access_screen"].fillna(0),
        ),
        "no_topography": (
            "Removes slope/elevation from transition pressure",
            minmax(0.45 * zones["mobility_pressure"].fillna(0) + 0.25 * zones["home_constraint_screen"].fillna(0) + 0.30 * vuln),
            zones["access_screen"].fillna(0),
        ),
    }
    rows = []
    for name, (reading, transition, access) in scenarios.items():
        transition = pd.Series(transition, index=zones.index).fillna(0)
        access = pd.Series(access, index=zones.index).fillna(0)
        disadv = minmax(transition * (1 - access)).fillna(0)
        rows.append(
            {
                "scenario": name,
                "reading": reading,
                "access_gini": gini(access),
                "disadvantage_gini": gini(disadv),
                "mean_access": float(access.mean()),
                "top10_jaccard": jaccard_top(base_disadv, disadv, n=10),
            }
        )
    robust = pd.DataFrame(rows)
    robust.to_csv(TABLES / "table_cities_robustness_summary.csv", index=False)
    display = robust.loc[
        robust["scenario"].isin(
            [
                "base",
                "no_activity_anchors",
                "euclidean_distance",
                "cargame_epm_only",
                "short_decay_8min",
                "wide_decay_16min",
                "topography_penalized_access",
                "no_vulnerability",
                "no_home_constraint",
                "no_topography",
            ]
        )
    ]
    rows_tex = [
        [
            latex_escape(row["scenario"].replace("_", " ")),
            fmt_num(row["access_gini"]),
            fmt_num(row["disadvantage_gini"]),
            fmt_num(row["top10_jaccard"]),
            latex_escape(row["reading"]),
        ]
        for _, row in display.iterrows()
    ]
    write_latex_table(
        TABLES / "table_cities_robustness_summary.tex",
        ["Scenario", "Access Gini", "Disadv. Gini", "Top-10 Jaccard", "Reading"],
        rows_tex,
        "lrrrp{0.42\\textwidth}",
    )
    return robust


def write_policy_validation_protocol() -> None:
    rows = [
        ["Public status", "Is the station openly usable?", "Source class and EPM/CargaME/OSM identity", "Confirm public access, schedule, payment methods, tariff, and access restrictions"],
        ["Connector service", "Can users actually charge?", "No connector-level public log in current screen", "Publish connector type, power, uptime/status, successful starts, failed starts, and occupancy"],
        ["Grid hosting", "Can the site be energized without hidden constraints?", "Utility/operator presence and candidate type", "EPM hosting-capacity check, transformer/feeder review, connection cost and upgrade requirement"],
        ["Parcel or curb authority", "Who can authorize installation?", "OSM fuel/parking candidates and planning context", "Parcel owner, curb manager, municipal permission, parking operation and public-space review"],
        ["Traffic safety", "Does charging add conflict at the street edge?", "Road-incident exposure and candidate map", "Road-safety audit, access/egress design, pedestrian conflict and queue management review"],
        ["Equity targeting", "Does the site improve transition readiness?", "Disadvantage, home constraint, vulnerability and topography screens", "Prioritize sites that improve access for home-constrained, vulnerable or ladera/peripheral territories"],
    ]
    pd.DataFrame(rows, columns=["gate", "question", "current_evidence", "minimum_validation"]).to_csv(
        TABLES / "table_cities_policy_validation_protocol.csv", index=False
    )
    rows_tex = [[latex_escape(c) for c in row] for row in rows]
    write_latex_table(
        TABLES / "table_cities_policy_validation_protocol.tex",
        ["Gate", "Decision question", "Current public evidence", "Minimum validation before deployment"],
        rows_tex,
        "p{0.13\\textwidth}p{0.20\\textwidth}p{0.25\\textwidth}p{0.34\\textwidth}",
    )


def write_key_metrics(zones: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame, candidate_leads: gpd.GeoDataFrame) -> None:
    metrics = {
        "charger_records": len(chargers),
        "zone_records": len(zones),
        "candidate_leads": len(candidate_leads),
        "mean_nearest_min": zones["nearest_charger_min"].mean(),
        "median_nearest_min": zones["nearest_charger_min"].median(),
        "max_nearest_min": zones["nearest_charger_min"].max(),
        "mean_nearest_km": zones["nearest_charger_km"].mean(),
        "median_nearest_km": zones["nearest_charger_km"].median(),
        "max_nearest_km": zones["nearest_charger_km"].max(),
        "access_gini": gini(zones["access_screen"]),
        "mean_slope_pct": zones["slope_mean_pct"].mean(),
        "top_disadvantage_zone": int(zones.sort_values("disadvantage_screen", ascending=False)["zone_id"].iloc[0]),
        "top_disadvantage_municipality": zones.sort_values("disadvantage_screen", ascending=False)["municipality"].iloc[0],
    }
    pd.DataFrame([metrics]).to_csv(TABLES / "cities_key_metrics.csv", index=False)


def write_results_tables(zones: gpd.GeoDataFrame, candidate_leads: gpd.GeoDataFrame, access_variants: dict[str, np.ndarray]) -> None:
    write_priority_zone_table(zones)
    write_access_extremes_table(zones)
    write_robustness_summary(zones, access_variants)
    write_policy_validation_protocol()
    write_key_metrics(zones, gpd.read_file(PROCESSED / "mapped_charger_evidence.gpkg") if (PROCESSED / "mapped_charger_evidence.gpkg").exists() else gpd.GeoDataFrame(), candidate_leads)


def set_bounds(ax: plt.Axes, bounds_m: tuple[float, float, float, float]) -> None:
    minx, miny, maxx, maxy = bounds_m
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_facecolor(BASE["canvas"])


def add_north_arrow(ax: plt.Axes, x: float = 0.94, y: float = 0.80) -> None:
    ax.annotate(
        "N",
        xy=(x, y + 0.065),
        xytext=(x, y),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color="#111827", lw=1.0),
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.60, pad=0.4),
        zorder=80,
    )


def add_scale_bar(ax: plt.Axes, length_km: int = 5, x: float = 0.06, y: float = 0.055) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length = length_km * 1000
    start_x = x0 + (x1 - x0) * x
    start_y = y0 + (y1 - y0) * y
    tick = (y1 - y0) * 0.009
    ax.plot([start_x, start_x + length], [start_y, start_y], color="#111827", lw=2.2, solid_capstyle="butt", zorder=90)
    ax.plot([start_x, start_x], [start_y - tick, start_y + tick], color="#111827", lw=1.2, zorder=90)
    ax.plot([start_x + length, start_x + length], [start_y - tick, start_y + tick], color="#111827", lw=1.2, zorder=90)
    ax.text(start_x + length / 2, start_y + tick * 1.9, f"{length_km} km", ha="center", va="bottom", fontsize=8, zorder=90)


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        0.015,
        0.985,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.86, pad=1.8),
        zorder=90,
    )


def add_colorbar(fig: plt.Figure, ax: plt.Axes, cmap: LinearSegmentedColormap, label: str) -> None:
    sm = ScalarMappable(norm=Normalize(vmin=0, vmax=1), cmap=cmap)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.030, pad=0.012)
    cb.set_label(label, fontsize=7.5)
    cb.ax.tick_params(labelsize=7, length=2)
    cb.outline.set_linewidth(0.4)


def plot_zone_metric(
    ax: plt.Axes,
    zones: gpd.GeoDataFrame,
    column: str,
    cmap: LinearSegmentedColormap,
    bounds_m: tuple[float, float, float, float],
    missing_label: str | None = None,
) -> None:
    local = subset_metric(zones, bounds_m)
    if local.empty:
        return
    missing = local[column].isna()
    if missing.any():
        local.loc[missing].plot(
            ax=ax,
            facecolor="#eceff1",
            edgecolor=BASE["boundary_light"],
            linewidth=0.25,
            hatch="////" if missing_label else None,
            zorder=1,
        )
    local.loc[~missing].plot(
        ax=ax,
        column=column,
        cmap=cmap,
        vmin=0,
        vmax=1,
        edgecolor="#ffffff",
        linewidth=0.38,
        zorder=2,
    )


def plot_base_polygons(ax: plt.Axes, zones: gpd.GeoDataFrame, bounds_m: tuple[float, float, float, float], alpha: float = 0.72) -> None:
    local = subset_metric(zones, bounds_m)
    if local.empty:
        return
    local.plot(ax=ax, facecolor=BASE["polygon"], edgecolor=BASE["boundary"], linewidth=0.35, alpha=alpha, zorder=1)


def plot_roads(ax: plt.Axes, roads: gpd.GeoDataFrame, bounds_m: tuple[float, float, float, float]) -> None:
    local = subset_metric(roads, bounds_m)
    if local.empty:
        return
    local.plot(ax=ax, color="#ffffff", linewidth=0.42, alpha=0.42, zorder=3)
    local.plot(ax=ax, color=BASE["road"], linewidth=0.18, alpha=0.58, zorder=4)
    major = local.loc[local.get("major", False).fillna(False)].copy()
    if not major.empty:
        major.plot(ax=ax, color="#ffffff", linewidth=0.82, alpha=0.50, zorder=5)
        major.plot(ax=ax, color=BASE["road_major"], linewidth=0.45, alpha=0.78, zorder=6)


def plot_chargers(ax: plt.Axes, chargers: gpd.GeoDataFrame, size: int = 48) -> None:
    local = to_metric(chargers)
    styles = {
        "CargaME": (BASE["cargame"], "o", size),
        "EPM": (BASE["epm"], "s", size),
        "OSM": (BASE["osm"], "^", int(size * 0.9)),
    }
    for source, group in local.groupby("source"):
        color, marker, markersize = styles.get(source, ("#333333", "o", size))
        group.plot(
            ax=ax,
            color=color,
            marker=marker,
            markersize=markersize,
            edgecolor="white",
            linewidth=0.5,
            alpha=0.95,
            zorder=20,
        )


def draw_common_map(ax: plt.Axes, zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, bounds_m: tuple[float, float, float, float]) -> None:
    set_bounds(ax, bounds_m)
    plot_base_polygons(ax, zones, bounds_m)
    plot_roads(ax, roads, bounds_m)
    add_north_arrow(ax)
    add_scale_bar(ax, 5, x=0.60, y=0.055)


def save_figure(fig: plt.Figure, filename: str, dpi: int = 300) -> None:
    out = FIGURES / filename
    fig.savefig(out, dpi=dpi, bbox_inches="tight", facecolor=BASE["page"])
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}")


def figure_evidence_base(zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> None:
    centralities = read_safe_geojson(RAW / "planning" / "geomedellin" / "centralities.geojson")
    lines = read_safe_geojson(RAW / "transport" / "geomedellin" / "mass_transport_lines.geojson")
    stations = read_safe_geojson(RAW / "transport" / "geomedellin" / "mass_transport_stations.geojson")
    bounds_m = metric_bounds()

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 6.7), gridspec_kw={"width_ratios": [0.72, 1.28]})
    fig.patch.set_facecolor(BASE["page"])
    ax0, ax1 = axes

    full_bounds = tuple(float(v) for v in to_metric(zones).total_bounds) if not zones.empty else bounds_m
    set_bounds(ax0, full_bounds)
    plot_base_polygons(ax0, zones, full_bounds, alpha=0.90)
    minx, miny, maxx, maxy = bounds_m
    ax0.add_patch(plt.Rectangle((minx, miny), maxx - minx, maxy - miny, fill=False, edgecolor="#b91c1c", linewidth=1.3, zorder=10))
    ax0.set_title("(a) Metropolitan frame", fontsize=10.5, pad=5)

    set_bounds(ax1, bounds_m)
    plot_base_polygons(ax1, zones, bounds_m, alpha=0.68)
    cent = subset_metric(centralities, bounds_m)
    if not cent.empty:
        cent.plot(ax=ax1, facecolor=BASE["centrality"], edgecolor="none", alpha=0.40, zorder=2)
    plot_roads(ax1, roads, bounds_m)
    sitva = subset_metric(lines, bounds_m)
    if not sitva.empty:
        sitva.plot(ax=ax1, color=BASE["sitva"], linewidth=1.55, alpha=0.88, zorder=9)
    station_m = subset_metric(stations, bounds_m)
    if not station_m.empty:
        station_m.plot(ax=ax1, color="#457b9d", markersize=12, alpha=0.80, zorder=11)
    plot_chargers(ax=ax1, chargers=chargers, size=42)
    add_north_arrow(ax1)
    add_scale_bar(ax1, 5)
    ax1.set_title("(b) Charging evidence, SITVA, roads, and centralities", fontsize=10.5, pad=5)

    handles = [
        Line2D([0], [0], color=BASE["sitva"], lw=2, label="Metro/SITVA lines"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#457b9d", markersize=5.5, label="Mass-transit stations"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BASE["cargame"], markersize=6.5, label="CargaME chargers"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=BASE["epm"], markersize=6.5, label="EPM chargers"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=BASE["osm"], markersize=6.5, label="OSM chargers"),
    ]
    ax1.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.92, fontsize=7.2)
    fig.suptitle("Medellin / Valle de Aburra transition-readiness evidence base", fontsize=13, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96], w_pad=0.5)
    save_figure(fig, "fig_cities01_evidence_base_map.png")


def figure_supply_sources(zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> None:
    fuel = read_fuel_candidates()
    parking = read_parking_candidates()
    bounds_m = metric_bounds()
    fig, ax = plt.subplots(figsize=(8.7, 8.0))
    fig.patch.set_facecolor(BASE["page"])
    draw_common_map(ax, zones, roads, bounds_m)
    parking_m = subset_metric(parking, bounds_m)
    if not parking_m.empty:
        parking_m.plot(ax=ax, color=BASE["parking"], markersize=3.5, alpha=0.20, label="OSM parking", zorder=8)
    fuel_m = subset_metric(fuel, bounds_m)
    if not fuel_m.empty:
        fuel_m.plot(ax=ax, marker="D", facecolor="none", edgecolor=BASE["fuel"], linewidth=0.65, markersize=14, alpha=0.72, label="Fuel candidates", zorder=10)
    plot_chargers(ax, chargers, size=54)
    handles = [
        Line2D([0], [0], marker="D", linestyle="None", markerfacecolor="none", markeredgecolor=BASE["fuel"], markersize=6, label="Fuel candidate"),
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor=BASE["parking"], markeredgecolor="none", alpha=0.45, markersize=5, label="Parking evidence"),
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor=BASE["cargame"], markeredgecolor="white", markersize=6.5, label="CargaME"),
        Line2D([0], [0], marker="s", linestyle="None", markerfacecolor=BASE["epm"], markeredgecolor="white", markersize=6.5, label="EPM"),
        Line2D([0], [0], marker="^", linestyle="None", markerfacecolor=BASE["osm"], markeredgecolor="white", markersize=6.5, label="OSM"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.92, fontsize=7.2)
    ax.set_title("Charging evidence and candidate universe", fontsize=11, pad=6)
    save_figure(fig, "fig_cities02_charging_supply_sources.png")


def figure_topography_sitva(zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> None:
    dem, extent_wgs = read_hgt_subset()
    lines = read_gtfs_shapes()
    stops = read_gtfs_stops()
    bounds_m = metric_bounds()
    fig, ax = plt.subplots(figsize=(8.7, 8.0))
    fig.patch.set_facecolor(BASE["page"])
    set_bounds(ax, bounds_m)
    if dem.size:
        ls = LightSource(azdeg=315, altdeg=45)
        shade = ls.hillshade(dem, vert_exag=0.65, dx=1, dy=1)
        ax.imshow(shade, extent=metric_extent(extent_wgs), origin="upper", cmap="Greys", alpha=0.30, zorder=0)
    plot_base_polygons(ax, zones, bounds_m, alpha=0.44)
    plot_roads(ax, roads, bounds_m)
    sitva = subset_metric(lines, bounds_m)
    if not sitva.empty:
        sitva.plot(ax=ax, color="#111111", linewidth=1.35, alpha=0.92, zorder=11)
    stops_m = subset_metric(stops, bounds_m)
    if not stops_m.empty:
        stops_m.plot(ax=ax, color=BASE["station"], markersize=12, edgecolor="#111111", linewidth=0.25, alpha=0.94, zorder=12)
    plot_chargers(ax, chargers, size=42)
    add_north_arrow(ax)
    add_scale_bar(ax, 5, x=0.60, y=0.055)
    handles = [
        Line2D([0], [0], color="#111111", lw=2, label="GTFS SITVA shapes"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BASE["station"], markeredgecolor="#111111", markersize=5.5, label="GTFS stops"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BASE["cargame"], markersize=6.5, label="CargaME"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=BASE["epm"], markersize=6.5, label="EPM"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=True, framealpha=0.92, fontsize=7.2)
    ax.set_title("Topography, SITVA anchors, and charging evidence", fontsize=11, pad=6)
    save_figure(fig, "fig_cities03_topography_sitva_context.png")


def figure_safety_candidate_context(zones: gpd.GeoDataFrame, roads: gpd.GeoDataFrame, chargers: gpd.GeoDataFrame) -> None:
    incidents = read_safe_geojson(RAW / "safety" / "geomedellin" / "traffic_incidents_2022_total.geojson")
    fuel = read_fuel_candidates()
    bounds_m = metric_bounds()
    fig, ax = plt.subplots(figsize=(8.7, 8.0))
    fig.patch.set_facecolor(BASE["page"])
    draw_common_map(ax, zones, roads, bounds_m)
    inc_m = subset_metric(incidents, bounds_m)
    if not inc_m.empty:
        sample = inc_m.sample(min(len(inc_m), 9000), random_state=42)
        sample.plot(ax=ax, color=BASE["safety"], markersize=2, alpha=0.105, zorder=7)
    fuel_m = subset_metric(fuel, bounds_m)
    if not fuel_m.empty:
        fuel_m.plot(ax=ax, marker="D", facecolor="none", edgecolor=BASE["fuel"], linewidth=0.60, markersize=13, alpha=0.62, zorder=10)
    plot_chargers(ax, chargers, size=42)
    handles = [
        Line2D([0], [0], marker=".", linestyle="None", color=BASE["safety"], alpha=0.45, markersize=7, label="2022 traffic incident"),
        Line2D([0], [0], marker="D", linestyle="None", markerfacecolor="none", markeredgecolor=BASE["fuel"], markersize=6, label="Fuel candidate"),
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor=BASE["cargame"], markeredgecolor="white", markersize=6.5, label="CargaME"),
        Line2D([0], [0], marker="s", linestyle="None", markerfacecolor=BASE["epm"], markeredgecolor="white", markersize=6.5, label="EPM"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.92, fontsize=7.2)
    ax.set_title("Safety exposure and conversion-ready candidate context", fontsize=11, pad=6)
    save_figure(fig, "fig_cities06_safety_candidate_context.png")


def figure_readiness_inequality_sequence(
    zones_screen: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    chargers: gpd.GeoDataFrame,
    candidate_leads: gpd.GeoDataFrame,
) -> None:
    bounds_m = metric_bounds()
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 10.2), gridspec_kw={"wspace": 0.14, "hspace": 0.16})
    fig.patch.set_facecolor(BASE["page"])
    ax_access, ax_disadv, ax_scatter, ax_lorenz = axes.ravel()

    for ax in [ax_access, ax_disadv]:
        set_bounds(ax, bounds_m)
        plot_roads(ax, roads, bounds_m)

    plot_zone_metric(ax_access, zones_screen, "access_screen", CMAPS["access"], bounds_m)
    plot_chargers(ax_access, chargers, size=25)
    add_colorbar(fig, ax_access, CMAPS["access"], "Current public charging access")
    ax_access.set_title("(a) Activity-compatible public charging access screen", loc="left", pad=5)
    add_north_arrow(ax_access, x=0.94, y=0.76)
    add_scale_bar(ax_access, 5, x=0.57, y=0.055)

    plot_zone_metric(ax_disadv, zones_screen, "disadvantage_screen", CMAPS["disadvantage"], bounds_m)
    leads_m = subset_metric(candidate_leads, bounds_m)
    if not leads_m.empty:
        leads_m.plot(
            ax=ax_disadv,
            marker="D",
            facecolor="none",
            edgecolor="#111827",
            linewidth=0.72,
            markersize=22,
            alpha=0.88,
            zorder=20,
        )
    add_colorbar(fig, ax_disadv, CMAPS["disadvantage"], "Charging disadvantage")
    ax_disadv.set_title("(b) Transition-disadvantage screen and validation leads", loc="left", pad=5)
    add_north_arrow(ax_disadv, x=0.94, y=0.76)
    add_scale_bar(ax_disadv, 5, x=0.57, y=0.055)

    scatter = zones_screen.dropna(subset=["access_screen", "vulnerability_screen"]).copy()
    if not scatter.empty:
        colors = scatter["disadvantage_screen"].fillna(0)
        ax_scatter.scatter(
            scatter["access_screen"],
            scatter["vulnerability_screen"],
            c=colors,
            cmap=CMAPS["disadvantage"],
            vmin=0,
            vmax=1,
            s=42,
            edgecolor="white",
            linewidth=0.5,
            alpha=0.92,
        )
        med_x = scatter["access_screen"].median()
        med_y = scatter["vulnerability_screen"].median()
        ax_scatter.axvline(med_x, color="#9aa4af", lw=0.8, ls="--")
        ax_scatter.axhline(med_y, color="#9aa4af", lw=0.8, ls="--")
        ax_scatter.text(
            0.03,
            0.94,
            "higher vulnerability\nlower access",
            transform=ax_scatter.transAxes,
            ha="left",
            va="top",
            fontsize=8,
            color=BASE["text"],
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.78, pad=2),
        )
    ax_scatter.set_xlim(-0.03, 1.03)
    ax_scatter.set_ylim(-0.03, 1.03)
    ax_scatter.set_xlabel("Public charging access screen")
    ax_scatter.set_ylabel("Vulnerability screen")
    ax_scatter.set_title("(c) Access-vulnerability trade-off", loc="left", pad=5)
    ax_scatter.grid(True, color="#dce2e7", lw=0.55)
    for spine in ["top", "right"]:
        ax_scatter.spines[spine].set_visible(False)

    pop, cum = lorenz_xy(zones_screen["access_screen"])
    access_gini = gini(zones_screen["access_screen"])
    ax_lorenz.plot([0, 1], [0, 1], color="#9aa4af", lw=0.8, ls="--", label="Equal access")
    ax_lorenz.plot(pop, cum, color=BASE["cargame"], lw=2.2, label=f"Access screen (Gini {access_gini:.2f})")
    ax_lorenz.fill_between(pop, cum, pop, color=BASE["cargame"], alpha=0.13)
    ax_lorenz.set_xlim(0, 1)
    ax_lorenz.set_ylim(0, 1)
    ax_lorenz.set_xlabel("Cumulative OD/SIT zones")
    ax_lorenz.set_ylabel("Cumulative access screen")
    ax_lorenz.set_title("(d) Inequality of current charging access", loc="left", pad=5)
    ax_lorenz.legend(loc="lower right", frameon=False)
    ax_lorenz.grid(True, color="#dce2e7", lw=0.55)
    for spine in ["top", "right"]:
        ax_lorenz.spines[spine].set_visible(False)

    handles = [
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor=BASE["cargame"], markeredgecolor="white", markersize=6, label="Existing charging evidence"),
        Line2D([0], [0], marker="D", linestyle="None", markerfacecolor="none", markeredgecolor="#111827", markersize=6, label="Candidate validation lead"),
        Patch(facecolor="#eceff1", edgecolor=BASE["boundary_light"], hatch="////", label="Vulnerability not harmonized"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.015))
    fig.suptitle("Readiness, vulnerability, and charging-disadvantage sequence", fontsize=13, y=0.985)
    save_figure(fig, "fig_cities04_readiness_inequality_sequence.png")


def figure_epm_use_trend() -> None:
    path = RAW / "chargers" / "epm_public_charging_use_2019_2025.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    month_map = {
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
    df["month_num"] = df["mes"].astype(str).str.lower().str.strip().map(month_map)
    df["year"] = pd.to_numeric(df["a_o"], errors="coerce")
    df["total"] = pd.to_numeric(df["total"], errors="coerce")
    df = df.dropna(subset=["year", "month_num", "total"]).copy()
    df["date"] = pd.to_datetime(dict(year=df["year"].astype(int), month=df["month_num"].astype(int), day=1))
    df = df.sort_values("date")
    df["cumulative_total"] = df["total"].cumsum()
    annual = df.groupby("year", as_index=False)["total"].sum()
    annual["year"] = annual["year"].astype(int)

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.4), gridspec_kw={"width_ratios": [0.92, 1.08], "wspace": 0.22})
    fig.patch.set_facecolor(BASE["page"])
    ax0, ax1 = axes
    colors = [BASE["cargame"] if y < 2025 else BASE["epm"] for y in annual["year"]]
    ax0.bar(annual["year"].astype(str), annual["total"], color=colors, width=0.68)
    ax0.set_title("(a) Annual reported use", loc="left", pad=5)
    ax0.set_ylabel("Reported total")
    ax0.tick_params(axis="x", rotation=0)
    ax0.grid(True, axis="y", color="#d9dee3", linewidth=0.6)
    partial = annual.loc[annual["year"] == 2025]
    if not partial.empty:
        y = float(partial["total"].iloc[0])
        ax0.text(len(annual) - 1, y + annual["total"].max() * 0.035, "partial", ha="center", va="bottom", color=BASE["muted"], fontsize=7.4)

    ax1.plot(df["date"], df["cumulative_total"], color=BASE["cargame"], linewidth=2.3)
    ax1.scatter(df["date"], df["cumulative_total"], color=BASE["epm"], s=14, zorder=3)
    correction = df.loc[df["total"] < 0]
    if not correction.empty:
        ax1.scatter(
            correction["date"],
            correction["cumulative_total"],
            facecolor="white",
            edgecolor=BASE["safety"],
            linewidth=0.8,
            s=34,
            zorder=4,
            label="Source correction month",
        )
        ax1.legend(loc="lower right", frameon=False)
    ax1.set_title("(b) Cumulative reported public charging use", loc="left", pad=5)
    ax1.set_ylabel("Cumulative reported total")
    ax1.set_xlabel("")
    ax1.grid(True, axis="y", color="#d9dee3", linewidth=0.6)
    for ax in axes:
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
    fig.suptitle("EPM public charging-use evidence", fontsize=12.5, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    save_figure(fig, "fig_cities05_epm_public_use_trend.png")


def write_map_manifest(chargers: gpd.GeoDataFrame, zones: gpd.GeoDataFrame) -> None:
    rows = [
        ("fig_cities01_evidence_base_map.png", "Opening territorial context: metropolitan frame, roads, SITVA, centralities, and charger sources."),
        ("fig_cities02_charging_supply_sources.png", "Observed charging evidence versus candidate opportunity on the same road-network base."),
        ("fig_cities03_topography_sitva_context.png", "Topography and intermodal anchors as the Medellin-specific access mechanism."),
        ("fig_cities04_readiness_inequality_sequence.png", "Integrated readiness, vulnerability, disadvantage, scatter, and Lorenz sequence."),
        ("fig_cities05_epm_public_use_trend.png", "Operational-use evidence showing charging as an active public urban service."),
        ("fig_cities06_safety_candidate_context.png", "Implementation screen linking candidates, safety exposure, roads, and existing supply."),
    ]
    manifest = pd.DataFrame(rows, columns=["file", "role"])
    manifest["charger_records_mapped"] = len(chargers)
    manifest["zone_records_mapped"] = len(zones)
    out = ROOT / "outputs" / "tables" / "figure_manifest.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(out, index=False)
    print(f"Saved {out.relative_to(ROOT)}")


def write_storyboard() -> None:
    path = ROOT / "docs" / "cities_editorial" / "cities_map_storyboard.md"
    text = """# Cities Map Storyboard

This storyboard defines the visual logic for the Medellin-Valle de Aburra paper.

## Cartographic Base

- Use a light grey analytical canvas, not an empty white background.
- Show OD/SIT polygons as pale filled geography with thin grey boundaries.
- Use the OSM drive graph as the local cartographic base: minor roads in light grey-blue and major roads darker.
- Keep maps north-up and add compact scale bars and north arrows where spatial scale matters.
- Separate evidence classes visually: CargaME circles, EPM squares, OSM triangles, candidates as hollow diamonds.
- Avoid implying that candidates are approved construction sites.

## Narrative Sequence

1. Evidence base: establish the metropolitan valley, road/SITVA structure, centralities, and charger sources.
2. Supply and candidate universe: separate observed charging evidence from possible implementation opportunity.
3. Topography and intermodality: show why Medellin is not a flat charger-count problem.
4. Readiness and inequality sequence: connect access, vulnerability, disadvantage, scatter diagnostics, and Lorenz/Gini in one visual argument.
5. Operational evidence: use EPM trends to show public charging as an active service while preserving reliability limits.
6. Safety and implementation: turn candidate maps into validation agendas instead of build lists.

## Cities Framing

The maps and charts should tell one climate-neutral urban-transition story. Accessibility remains a method component, but every figure should advance the same question: where is electric mobility usable, equitable, reliable, and implementable across the metropolitan valley?
"""
    path.write_text(text, encoding="utf-8")
    print(f"Saved {path.relative_to(ROOT)}")


def main() -> None:
    ensure_dirs()
    zones = read_amva_zones()
    roads = read_roads()
    chargers = read_chargers()
    if not chargers.empty:
        chargers_m = to_metric(chargers).copy()
        chargers_m["activity_anchor_score"] = activity_anchor_scores(chargers_m.geometry)
        chargers_m.to_file(PROCESSED / "mapped_charger_evidence.gpkg", driver="GPKG")
    if not zones.empty:
        to_metric(zones).to_file(PROCESSED / "mapped_amva_zones.gpkg", driver="GPKG")
    zones_screen, candidate_leads = build_readiness_screen(zones, chargers)

    figure_evidence_base(zones, roads, chargers)
    figure_supply_sources(zones, roads, chargers)
    figure_topography_sitva(zones, roads, chargers)
    figure_safety_candidate_context(zones, roads, chargers)
    figure_epm_use_trend()
    figure_readiness_inequality_sequence(zones_screen, roads, chargers, candidate_leads)
    write_map_manifest(chargers, zones)
    write_storyboard()


if __name__ == "__main__":
    main()
