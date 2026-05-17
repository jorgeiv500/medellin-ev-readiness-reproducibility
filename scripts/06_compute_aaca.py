from __future__ import annotations

import numpy as np
import geopandas as gpd
import networkx as nx
import osmnx as ox

from aaca_utils import ROOT, load_yaml, minmax


def nearest_graph_nodes(graph, geoms: gpd.GeoSeries) -> list[int]:
    if graph is None or geoms.empty:
        return []
    geoms_wgs = geoms.to_crs("EPSG:4326")
    return list(ox.distance.nearest_nodes(graph, X=geoms_wgs.x.to_numpy(), Y=geoms_wgs.y.to_numpy()))


def network_cost_matrix(
    graph,
    origin_nodes: list[int],
    destination_nodes: list[int],
    weight: str,
    cutoff: float | None = None,
) -> np.ndarray:
    if graph is None or not origin_nodes or not destination_nodes:
        return np.empty((len(origin_nodes), len(destination_nodes)))
    matrix = np.full((len(origin_nodes), len(destination_nodes)), np.nan, dtype=float)
    for i, origin in enumerate(origin_nodes):
        costs = nx.single_source_dijkstra_path_length(graph, origin, cutoff=cutoff, weight=weight)
        matrix[i, :] = [costs.get(destination, np.nan) for destination in destination_nodes]
    return matrix


def euclidean_travel_minutes(distances_m: np.ndarray, speed_kph: float) -> np.ndarray:
    return distances_m / 1000.0 / speed_kph * 60.0


def main() -> None:
    params = load_yaml("config/parameters.yml")
    units_path = ROOT / "data_processed/transition_need.gpkg"
    if not units_path.exists():
        units_path = ROOT / "data_processed/readiness_screen.gpkg"
    chargers_path = ROOT / "data_processed/chargers_clean.gpkg"
    if not chargers_path.exists():
        chargers_path = ROOT / "data_processed/mapped_charger_evidence.gpkg"
    graph_path = ROOT / "data_processed/road_network.graphml"

    if not units_path.exists() or not chargers_path.exists():
        print("Missing transition/readiness units or charger evidence.")
        return

    units = gpd.read_file(units_path).to_crs(params["project"]["crs_projected"])
    chargers = gpd.read_file(chargers_path).to_crs(params["project"]["crs_projected"])

    if "transition_need" not in units.columns:
        if "transition_pressure" in units.columns:
            units["transition_need"] = units["transition_pressure"]
        else:
            print("transition_need not found. Filling with 0 until transition variables are joined.")
            units["transition_need"] = 0.0
    if "vulnerability" not in units.columns and "vulnerability_screen" in units.columns:
        units["vulnerability"] = units["vulnerability_screen"]

    source_col = "source" if "source" in chargers.columns else "fuente" if "fuente" in chargers.columns else None
    if "source_reliability" not in chargers.columns:
        reliability = params["charger_cleaning"]["reliability"]
        chargers["source_reliability"] = chargers[source_col].map(reliability).fillna(0.5) if source_col else 0.5
    if "capacity_proxy" not in chargers.columns:
        if "conectores" in chargers.columns:
            chargers["capacity_proxy"] = chargers["conectores"].fillna(1).clip(lower=1)
        else:
            chargers["capacity_proxy"] = 1.0

    if "activity_anchor_score" not in chargers.columns:
        print("activity_anchor_score not found on chargers. Using 0 until 04_build_activity_anchors.py computes joins.")
        chargers["activity_anchor_score"] = 0.0

    decay = params["aaca"]["decay_minutes"]
    base = params["aaca"]["anchor_base"]
    multiplier = params["aaca"]["anchor_multiplier"]

    unit_points = units.geometry.representative_point()
    euclidean_m = np.vstack([chargers.geometry.distance(point).to_numpy(dtype=float) for point in unit_points])
    travel_min = euclidean_travel_minutes(euclidean_m, params["network"]["default_speed_kph"])
    network_km = euclidean_m / 1000.0
    impedance_method = "euclidean_time_fallback"

    if graph_path.exists():
        graph = ox.load_graphml(graph_path)
        unit_nodes = nearest_graph_nodes(graph, gpd.GeoSeries(unit_points, crs=units.crs))
        charger_nodes = nearest_graph_nodes(graph, chargers.geometry)
        network_time_s = network_cost_matrix(graph, unit_nodes, charger_nodes, weight="travel_time", cutoff=4 * 60 * 60)
        if network_time_s.shape == travel_min.shape and np.isfinite(network_time_s).any():
            travel_min = network_time_s / 60.0
            impedance_method = "osm_drive_network_travel_time"
            network_length_m = network_cost_matrix(graph, unit_nodes, charger_nodes, weight="length", cutoff=120000)
            if network_length_m.shape == travel_min.shape and np.isfinite(network_length_m).any():
                network_km = network_length_m / 1000.0
    else:
        print("Missing road_network.graphml. Falling back to Euclidean travel-time proxy.")

    weights = (
        chargers["capacity_proxy"].fillna(1).to_numpy(dtype=float)
        * chargers["source_reliability"].fillna(0.5).to_numpy(dtype=float)
        * (base + multiplier * chargers["activity_anchor_score"].fillna(0).to_numpy(dtype=float))
    )
    valid = np.isfinite(travel_min)
    contributions = np.zeros_like(travel_min, dtype=float)
    contributions[valid] = np.exp(-travel_min[valid] / decay)
    scores = contributions @ weights

    units["aaca_score"] = scores
    units["aaca_norm"] = minmax(units["aaca_score"])
    units["impedance_method"] = impedance_method
    units["nearest_charger_network_min"] = np.nanmin(travel_min, axis=1)
    units["nearest_charger_network_km"] = np.nanmin(network_km, axis=1)
    units["aaca_decay_minutes"] = decay
    # Transition need already carries the vulnerability signal in the Medellin
    # screen, so the access gap is not multiplied by vulnerability again.
    units["desert_score"] = units["transition_need"].fillna(0) * (1 - units["aaca_norm"].fillna(0))

    out = ROOT / "data_processed/aaca_scores.gpkg"
    units.to_file(out, driver="GPKG")
    print(f"Saved AACA and desert scores to {out}")
    print(f"Impedance method: {impedance_method}")


if __name__ == "__main__":
    main()
