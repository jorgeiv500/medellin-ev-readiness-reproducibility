"""
Build an enriched candidate universe for Medellin EV-charging counterfactuals.

The earlier draft used a small candidate list. For a Cities-style experiment we
need a broader and auditable opportunity set that reflects urban implementation
choices: fuel-station conversions, parking facilities, metro/SITVA nodes,
centralities and public facilities. This script creates that universe, excludes
sites already close to mapped chargers, and adds implementation/activity scores
used by the counterfactual experiment.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
PROCESSED = ROOT / "data_processed"
TABLES = ROOT / "outputs" / "tables"

WGS84 = "EPSG:4326"
METRIC = "EPSG:3116"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^0-9a-zA-Z]+", "_", value).strip("_").lower()
    return value or "unnamed"


def find_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def read_vector(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(WGS84)


def overpass_points(path: Path, candidate_type: str, source: str) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame(columns=["candidate_type", "source", "name", "geometry"], crs=WGS84)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {}) or {}
        lon = element.get("lon")
        lat = element.get("lat")
        if lon is None or lat is None:
            center = element.get("center") or {}
            lon = center.get("lon")
            lat = center.get("lat")
        if lon is None or lat is None:
            bounds = element.get("bounds") or {}
            if {"minlon", "maxlon", "minlat", "maxlat"} <= set(bounds):
                lon = (bounds["minlon"] + bounds["maxlon"]) / 2
                lat = (bounds["minlat"] + bounds["maxlat"]) / 2
        if lon is None or lat is None:
            continue
        rows.append(
            {
                "candidate_type": candidate_type,
                "source": source,
                "name": tags.get("name") or tags.get("operator") or candidate_type,
                "operator": tags.get("operator"),
                "osm_id": f"{element.get('type', 'node')}/{element.get('id')}",
                "geometry": Point(float(lon), float(lat)),
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84)


def representative_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = gdf.to_crs(METRIC).representative_point().to_crs(WGS84)
    return gdf


def safe_name_column(gdf: gpd.GeoDataFrame) -> pd.Series:
    candidates = [
        c
        for c in gdf.columns
        if c.lower() in {"nombre", "name", "nom_estacion", "estacion", "nombreequipamiento", "equipamiento"}
    ]
    if candidates:
        return gdf[candidates[0]].astype(str)
    return pd.Series([""] * len(gdf), index=gdf.index)


def load_geomedellin_candidates() -> list[gpd.GeoDataFrame]:
    layers = []

    centralities = find_existing(
        [
            RAW / "planning" / "geomedellin" / "centralities.geojson",
            RAW / "planning" / "geomedellin" / "centralities.gpkg",
            RAW / "planning" / "geomedellin" / "centralities" / "centralities.geojson",
            RAW / "planning" / "geomedellin" / "centralities" / "centralities.gpkg",
        ]
    )
    if centralities:
        gdf = representative_points(read_vector(centralities))
        layers.append(
            gpd.GeoDataFrame(
                {
                    "candidate_type": "centrality",
                    "source": "GeoMedellin",
                    "name": safe_name_column(gdf),
                    "geometry": gdf.geometry,
                },
                crs=WGS84,
            )
        )

    stations = find_existing(
        [
            RAW / "transport" / "geomedellin" / "mass_transport_stations.geojson",
            RAW / "transport" / "geomedellin" / "mass_transport_stations.gpkg",
            RAW / "transport" / "geomedellin" / "mass_transport_stations" / "mass_transport_stations.geojson",
            RAW / "transport" / "geomedellin" / "mass_transport_stations" / "mass_transport_stations.gpkg",
        ]
    )
    if stations:
        gdf = read_vector(stations)
        if not all(gdf.geom_type == "Point"):
            gdf = representative_points(gdf)
        layers.append(
            gpd.GeoDataFrame(
                {
                    "candidate_type": "sitva_node",
                    "source": "GeoMedellin",
                    "name": safe_name_column(gdf),
                    "geometry": gdf.geometry,
                },
                crs=WGS84,
            )
        )

    for folder, ctype in [
        ("collective_facilities", "public_facility"),
        ("collective_facilities_categories", "public_facility"),
        ("higher_education_institutions", "university"),
        ("higher_education", "university"),
        ("education_sites", "education"),
    ]:
        path = find_existing(
            [
                RAW / "activity" / "geomedellin" / f"{folder}.geojson",
                RAW / "activity" / "geomedellin" / f"{folder}.gpkg",
                RAW / "planning" / "geomedellin" / f"{folder}.geojson",
                RAW / "planning" / "geomedellin" / f"{folder}.gpkg",
                RAW / "activity" / "geomedellin" / folder / f"{folder}.geojson",
                RAW / "activity" / "geomedellin" / folder / f"{folder}.gpkg",
            ]
        )
        if not path:
            continue
        gdf = read_vector(path)
        if not all(gdf.geom_type == "Point"):
            gdf = representative_points(gdf)
        layers.append(
            gpd.GeoDataFrame(
                {
                    "candidate_type": ctype,
                    "source": "GeoMedellin",
                    "name": safe_name_column(gdf),
                    "geometry": gdf.geometry,
                },
                crs=WGS84,
            )
        )

    return layers


def load_substations() -> gpd.GeoDataFrame:
    path = RAW / "electric" / "upme_substations_national_raw.json"
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], crs=WGS84)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        attrs = feature.get("attributes", {}) or {}
        geom = feature.get("geometry", {}) or {}
        lon = attrs.get("LONGITUD") or attrs.get("longitud") or geom.get("x")
        lat = attrs.get("LATITUD") or attrs.get("latitud") or geom.get("y")
        if lon is None or lat is None:
            continue
        try:
            lon_f, lat_f = float(lon), float(lat)
        except Exception:
            continue
        # Keep only Antioquia/Aburra-region candidates by generous bbox.
        if -76.9 <= lon_f <= -74.5 and 5.4 <= lat_f <= 7.4:
            rows.append({"name": attrs.get("NOM_SUBESTACION"), "geometry": Point(lon_f, lat_f)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84)


def nearest_distance(left: gpd.GeoDataFrame, right: gpd.GeoDataFrame, name: str) -> pd.Series:
    if right.empty or left.empty:
        return pd.Series(np.nan, index=left.index, name=name)
    left_m = left.to_crs(METRIC).reset_index().rename(columns={"index": "_left_index"})
    right_m = right.to_crs(METRIC)[["geometry"]].reset_index(drop=True)
    joined = gpd.sjoin_nearest(left_m[["_left_index", "geometry"]], right_m, how="left", distance_col=name)
    distances = joined.groupby("_left_index")[name].min()
    return left.index.to_series().map(distances).astype(float)


def exp_score(distance_m: pd.Series, scale_m: float) -> pd.Series:
    return np.exp(-distance_m.fillna(999999) / scale_m).clip(0, 1)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    zones = read_vector(PROCESSED / "readiness_story_screen.gpkg")
    zones_m = zones.to_crs(METRIC)
    study_area = zones_m.unary_union.buffer(1500)

    layers = [
        overpass_points(RAW / "osm" / "overpass_fuel_stations.json", "fuel_station", "OSM"),
        overpass_points(RAW / "osm" / "overpass_parking.json", "parking", "OSM"),
        overpass_points(RAW / "osm" / "overpass_activity_anchors.json", "commercial_or_activity_anchor", "OSM"),
    ]
    layers.extend(load_geomedellin_candidates())
    candidates = pd.concat([gdf for gdf in layers if not gdf.empty], ignore_index=True)
    candidates = gpd.GeoDataFrame(candidates, geometry="geometry", crs=WGS84)
    candidates = candidates[candidates.geometry.notna()].copy()

    candidates_m = candidates.to_crs(METRIC)
    candidates = candidates.loc[candidates_m.geometry.within(study_area)].copy()
    candidates_m = candidates.to_crs(METRIC)

    chargers = read_vector(PROCESSED / "mapped_charger_evidence.gpkg")
    candidates["dist_existing_charger_m"] = nearest_distance(candidates, chargers, "dist_existing_charger_m")
    candidates = candidates[candidates["dist_existing_charger_m"].fillna(999999) >= 300].copy()

    sitva = candidates[candidates["candidate_type"].eq("sitva_node")].copy()
    centrality = candidates[candidates["candidate_type"].eq("centrality")].copy()
    public_facility = candidates[candidates["candidate_type"].isin(["public_facility", "university", "education"])].copy()
    substations = load_substations()

    # Road proximity is approximated by the existing candidate-source semantics
    # when no separate road-line layer is needed for the counterfactual. Fuel and
    # parking sites already encode road-facing implementation opportunity.
    candidates["dist_sitva_m"] = nearest_distance(candidates, sitva, "dist_sitva_m")
    candidates["dist_centrality_m"] = nearest_distance(candidates, centrality, "dist_centrality_m")
    candidates["dist_public_facility_m"] = nearest_distance(candidates, public_facility, "dist_public_facility_m")
    candidates["dist_substation_m"] = nearest_distance(candidates, substations, "dist_substation_m")

    zones_small = zones[
        [
            "zone_id",
            "transition_pressure",
            "vulnerability_screen",
            "home_constraint_screen",
            "topography_burden_screen",
            "network_penalty_screen",
            "geometry",
        ]
    ].copy()
    joined = gpd.sjoin(
        candidates.to_crs(METRIC),
        zones_small.to_crs(METRIC),
        how="left",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")
    candidates = joined.to_crs(WGS84)

    type_feasibility = {
        "fuel_station": 0.95,
        "parking": 0.86,
        "sitva_node": 0.72,
        "centrality": 0.62,
        "public_facility": 0.60,
        "university": 0.58,
        "education": 0.50,
        "commercial_or_activity_anchor": 0.55,
    }
    type_activity = {
        "fuel_station": 0.25,
        "parking": 0.35,
        "sitva_node": 0.95,
        "centrality": 0.85,
        "public_facility": 0.72,
        "university": 0.78,
        "education": 0.62,
        "commercial_or_activity_anchor": 0.70,
    }

    candidates["type_feasibility"] = candidates["candidate_type"].map(type_feasibility).fillna(0.50)
    candidates["type_activity"] = candidates["candidate_type"].map(type_activity).fillna(0.50)
    candidates["activity_score"] = (
        0.35 * exp_score(candidates["dist_sitva_m"], 650)
        + 0.25 * exp_score(candidates["dist_centrality_m"], 900)
        + 0.15 * exp_score(candidates["dist_public_facility_m"], 650)
        + 0.25 * candidates["type_activity"]
    ).clip(0, 1)
    candidates["low_topography_score"] = 1 - candidates["topography_burden_screen"].fillna(0.5).clip(0, 1)
    candidates["implementation_score"] = (
        0.32 * candidates["type_feasibility"]
        + 0.26 * exp_score(candidates["dist_substation_m"], 2500)
        + 0.22 * candidates["low_topography_score"]
        + 0.20 * exp_score(candidates["dist_existing_charger_m"], 1400)
    ).clip(0, 1)
    candidates["trap_exposure_score"] = (
        0.42 * candidates["transition_pressure"].fillna(0)
        + 0.24 * candidates["vulnerability_screen"].fillna(0)
        + 0.20 * candidates["home_constraint_screen"].fillna(0)
        + 0.14 * candidates["network_penalty_screen"].fillna(0)
    ).clip(0, 1)
    candidates["market_readiness_score"] = (
        0.55 * candidates["implementation_score"]
        + 0.25 * candidates["activity_score"]
        + 0.20 * candidates["low_topography_score"]
    ).clip(0, 1)

    # Remove near-identical candidates while preserving implementable site types.
    type_priority = {
        "fuel_station": 1,
        "parking": 2,
        "sitva_node": 3,
        "centrality": 4,
        "public_facility": 5,
        "university": 6,
        "education": 7,
        "commercial_or_activity_anchor": 8,
    }
    candidates_m = candidates.to_crs(METRIC)
    candidates_m["snap_x"] = (candidates_m.geometry.x / 120).round().astype(int)
    candidates_m["snap_y"] = (candidates_m.geometry.y / 120).round().astype(int)
    candidates_m["type_priority"] = candidates_m["candidate_type"].map(type_priority).fillna(9)
    candidates_m = candidates_m.sort_values(
        ["snap_x", "snap_y", "type_priority", "market_readiness_score"],
        ascending=[True, True, True, False],
    )
    candidates_m = candidates_m.drop_duplicates(["snap_x", "snap_y"], keep="first")
    candidates = candidates_m.drop(columns=["snap_x", "snap_y", "type_priority"]).to_crs(WGS84)

    keep_cols = [
        "candidate_type",
        "source",
        "name",
        "operator",
        "osm_id",
        "zone_id",
        "dist_existing_charger_m",
        "dist_sitva_m",
        "dist_centrality_m",
        "dist_public_facility_m",
        "dist_substation_m",
        "activity_score",
        "implementation_score",
        "trap_exposure_score",
        "market_readiness_score",
        "low_topography_score",
        "geometry",
    ]
    for col in keep_cols:
        if col not in candidates.columns:
            candidates[col] = pd.NA
    candidates = candidates[keep_cols].copy()
    candidates["candidate_id"] = [f"cand_{i:04d}" for i in range(1, len(candidates) + 1)]

    out_path = PROCESSED / "counterfactual_candidate_universe.gpkg"
    candidates.to_file(out_path, driver="GPKG")

    summary = (
        candidates.groupby("candidate_type")
        .agg(
            candidates=("candidate_id", "count"),
            mean_activity=("activity_score", "mean"),
            mean_implementation=("implementation_score", "mean"),
            mean_trap_exposure=("trap_exposure_score", "mean"),
        )
        .reset_index()
        .sort_values("candidates", ascending=False)
    )
    summary.to_csv(TABLES / "table_counterfactual_candidate_universe.csv", index=False)

    print(f"Wrote {out_path.relative_to(ROOT)} with {len(candidates):,} candidate sites")
    print(f"Wrote outputs/tables/table_counterfactual_candidate_universe.csv")


if __name__ == "__main__":
    main()
