"""
Run the core Cities counterfactual experiment.

This is not framed as an electrical-engineering siting optimizer. It is a
territorial experiment: under the same public-data opportunity set, which
planning rule corrects the readiness trap and which rule reproduces it?

The script uses a transparent greedy approximation to the p-site problem. Each
candidate is evaluated by marginal reduction in a transition-disadvantage
surface plus a scenario-specific urban-quality term. The output is intended for
editorial interpretation and robustness, not as a deployment-ready build list.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data_processed"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

WGS84 = "EPSG:4326"
METRIC = "EPSG:3116"
BUDGET = 20
DECAY_MIN = 12.0
GAIN_SCALE = 0.18


def minmax(values: pd.Series | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    finite = np.isfinite(arr)
    out = np.zeros_like(arr, dtype=float)
    if not finite.any():
        return out
    lo = np.nanmin(arr[finite])
    hi = np.nanmax(arr[finite])
    if math.isclose(hi, lo):
        out[finite] = 0.0
    else:
        out[finite] = (arr[finite] - lo) / (hi - lo)
    return np.clip(out, 0, 1)


def gini(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    x = np.asarray(values, dtype=float)
    if weights is None:
        weights = np.ones_like(x)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]
    if len(x) == 0 or np.allclose(x, 0):
        return float("nan")
    order = np.argsort(x)
    x = x[order]
    w = w[order]
    cumw = np.cumsum(w)
    cumxw = np.cumsum(x * w)
    return float(1 - 2 * np.trapz(cumxw / cumxw[-1], cumw / cumw[-1]))


def load_graph() -> nx.MultiDiGraph:
    graph_path = PROCESSED / "road_network.graphml"
    if not graph_path.exists():
        graph_path = PROCESSED / "road_network.graphml.xml"
    if not graph_path.exists():
        raise FileNotFoundError("data_processed/road_network.graphml or .graphml.xml is required")
    graph = ox.load_graphml(graph_path)
    for _, _, _, data in graph.edges(keys=True, data=True):
        length_m = float(data.get("length", 0) or 0)
        if "travel_time_min" in data:
            data["weight_min"] = float(data["travel_time_min"])
        elif "travel_time" in data:
            data["weight_min"] = float(data["travel_time"]) / 60.0
        else:
            speed_kph = float(data.get("speed_kph", 25) or 25)
            data["weight_min"] = (length_m / 1000.0) / max(speed_kph, 5.0) * 60.0
    return graph


def nearest_nodes(graph: nx.MultiDiGraph, gdf: gpd.GeoDataFrame) -> list:
    points = gdf.to_crs(WGS84)
    xs = points.geometry.x.to_numpy()
    ys = points.geometry.y.to_numpy()
    return ox.distance.nearest_nodes(graph, xs, ys)


def compute_time_matrix(
    graph: nx.MultiDiGraph, zones: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame, cutoff_min: float = 45.0
) -> np.ndarray:
    zone_nodes = nearest_nodes(graph, zones)
    candidate_nodes = np.asarray(nearest_nodes(graph, candidates))
    matrix = np.full((len(zones), len(candidates)), np.inf, dtype=float)
    for i, node in enumerate(zone_nodes):
        lengths = nx.single_source_dijkstra_path_length(
            graph, node, cutoff=cutoff_min, weight="weight_min"
        )
        for j, cand_node in enumerate(candidate_nodes):
            value = lengths.get(cand_node)
            if value is not None:
                matrix[i, j] = float(value)
    return matrix


def disadvantage(access: np.ndarray, zones: gpd.GeoDataFrame) -> np.ndarray:
    need = zones["transition_pressure"].fillna(0).to_numpy(dtype=float)
    # Vulnerability, home-charging constraint and topography enter the baseline
    # through transition_pressure. The scenario screen therefore applies access
    # change to that need surface without a second social multiplier.
    return need * (1 - np.clip(access, 0, 1))


def scenario_definitions(zones: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame, base_d: np.ndarray) -> dict:
    zone_arrays = {
        "need": zones["transition_pressure"].fillna(0).to_numpy(dtype=float),
        "home": zones["home_constraint_screen"].fillna(0).to_numpy(dtype=float),
        "topography": zones["topography_burden_screen"].fillna(0).to_numpy(dtype=float),
        "network": zones["network_penalty_screen"].fillna(0).to_numpy(dtype=float),
        "mobility": zones["mobility_pressure"].fillna(0).to_numpy(dtype=float),
        "base_d": minmax(base_d),
    }
    # Vulnerability is already part of transition_pressure. Scenario rules use
    # that composite need term instead of adding vulnerability again.
    cand_arrays = {
        "implementation": candidates["implementation_score"].fillna(0).to_numpy(dtype=float),
        "activity": candidates["activity_score"].fillna(0).to_numpy(dtype=float),
        "market": candidates["market_readiness_score"].fillna(0).to_numpy(dtype=float),
        "trap": candidates["trap_exposure_score"].fillna(0).to_numpy(dtype=float),
        "low_topography": candidates["low_topography_score"].fillna(0).to_numpy(dtype=float),
    }
    return {
        "coverage_first": {
            "label": "Coverage-first",
            "alpha": 0.82,
            "quality_weight": 0.18,
            "zone_weight": 0.55 + 0.25 * zone_arrays["need"] + 0.20 * zone_arrays["mobility"],
            "candidate_quality": 0.55 * cand_arrays["activity"] + 0.45 * cand_arrays["market"],
        },
        "market_ready": {
            "label": "Market-ready",
            "alpha": 0.36,
            "quality_weight": 0.64,
            "zone_weight": 0.55 + 0.35 * zone_arrays["need"] + 0.10 * zone_arrays["mobility"],
            "candidate_quality": cand_arrays["implementation"],
        },
        "mobility_hub": {
            "label": "Mobility-hub",
            "alpha": 0.45,
            "quality_weight": 0.55,
            "zone_weight": 0.45 + 0.45 * zone_arrays["mobility"] + 0.10 * zone_arrays["need"],
            "candidate_quality": cand_arrays["activity"],
        },
        "equity_transition": {
            "label": "Equity-transition",
            "alpha": 0.84,
            "quality_weight": 0.16,
            "zone_weight": (
                0.45
                + 0.45 * zone_arrays["need"]
                + 0.25 * zone_arrays["home"]
                + 0.25 * zone_arrays["topography"]
                + 0.30 * zone_arrays["base_d"]
            ),
            "candidate_quality": 0.55 * cand_arrays["trap"] + 0.25 * cand_arrays["implementation"] + 0.20 * cand_arrays["activity"],
        },
        "balanced_governance": {
            "label": "Balanced-governance",
            "alpha": 0.66,
            "quality_weight": 0.34,
            "zone_weight": (
                0.50
                + 0.35 * zone_arrays["need"]
                + 0.18 * zone_arrays["home"]
                + 0.15 * zone_arrays["network"]
            ),
            "candidate_quality": (
                0.35 * cand_arrays["implementation"]
                + 0.30 * cand_arrays["activity"]
                + 0.20 * cand_arrays["trap"]
                + 0.15 * cand_arrays["low_topography"]
            ),
        },
    }


def run_greedy(
    scenario: dict,
    zones: gpd.GeoDataFrame,
    candidates: gpd.GeoDataFrame,
    gain_matrix: np.ndarray,
    base_access: np.ndarray,
    budget: int,
) -> tuple[list[int], np.ndarray, list[dict]]:
    selected: list[int] = []
    selected_mask = np.zeros(gain_matrix.shape[1], dtype=bool)
    cumulative_gain = np.zeros(gain_matrix.shape[0], dtype=float)
    current_access = np.clip(base_access, 0, 1)
    current_d = disadvantage(current_access, zones)
    trace = []

    zone_weight = np.asarray(scenario["zone_weight"], dtype=float)
    candidate_quality = minmax(np.asarray(scenario["candidate_quality"], dtype=float))

    for rank in range(1, budget + 1):
        proposal_gain = cumulative_gain[:, None] + gain_matrix
        proposal_access = np.clip(base_access[:, None] + GAIN_SCALE * proposal_gain, 0, 1)
        proposed_d = np.apply_along_axis(disadvantage, 0, proposal_access, zones)
        marginal = ((current_d[:, None] - proposed_d) * zone_weight[:, None]).sum(axis=0)
        marginal[selected_mask] = -np.inf

        marginal_norm = minmax(marginal)
        score = scenario["alpha"] * marginal_norm + scenario["quality_weight"] * candidate_quality
        score[selected_mask] = -np.inf
        choice = int(np.nanargmax(score))
        selected.append(choice)
        selected_mask[choice] = True
        cumulative_gain += gain_matrix[:, choice]
        current_access = np.clip(base_access + GAIN_SCALE * cumulative_gain, 0, 1)
        current_d = disadvantage(current_access, zones)
        trace.append(
            {
                "rank": rank,
                "candidate_id": candidates.iloc[choice]["candidate_id"],
                "candidate_type": candidates.iloc[choice]["candidate_type"],
                "marginal_weighted_reduction": float(marginal[choice]),
                "selection_score": float(score[choice]),
            }
        )
    return selected, current_access, trace


def metric_row(
    scenario_name: str,
    label: str,
    zones: gpd.GeoDataFrame,
    candidates: gpd.GeoDataFrame,
    selected: list[int],
    base_access: np.ndarray,
    scenario_access: np.ndarray,
    base_d: np.ndarray,
    scenario_d: np.ndarray,
) -> dict:
    reduction = base_d - scenario_d
    trap_threshold = np.nanquantile(base_d, 0.75)
    initial_traps = base_d >= trap_threshold
    high_readiness = (base_access >= np.nanmedian(base_access)) & (base_d <= np.nanmedian(base_d))
    ladera = zones["topography_burden_screen"].fillna(0).to_numpy(dtype=float) >= np.nanmedian(
        zones["topography_burden_screen"].fillna(0).to_numpy(dtype=float)
    )
    total_reduction = np.nansum(np.maximum(reduction, 0))
    selected_gdf = candidates.iloc[selected]
    trap_reduction = np.nansum(np.maximum(reduction[initial_traps], 0))
    readiness_reduction = np.nansum(np.maximum(reduction[high_readiness], 0))
    return {
        "scenario": scenario_name,
        "label": label,
        "budget": len(selected),
        "mean_disadvantage_before": float(np.nanmean(base_d)),
        "mean_disadvantage_after": float(np.nanmean(scenario_d)),
        "mean_reduction": float(np.nanmean(reduction)),
        "top_quartile_mean_reduction": float(np.nanmean(reduction[initial_traps])),
        "trap_dissolution_rate": float(np.mean(scenario_d[initial_traps] < trap_threshold)),
        "benefit_capture_ratio_ready_over_trap": float(readiness_reduction / trap_reduction)
        if trap_reduction > 0
        else float("nan"),
        "spatial_leakage_index": float(
            np.nansum(np.maximum(reduction[~initial_traps], 0)) / total_reduction
        )
        if total_reduction > 0
        else float("nan"),
        "ladera_minus_valley_reduction": float(np.nanmean(reduction[ladera]) - np.nanmean(reduction[~ladera])),
        "residual_disadvantage_gini": gini(scenario_d),
        "mean_selected_activity": float(selected_gdf["activity_score"].mean()),
        "mean_selected_implementation": float(selected_gdf["implementation_score"].mean()),
        "mean_selected_trap_exposure": float(selected_gdf["trap_exposure_score"].mean()),
    }


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    zones = gpd.read_file(PROCESSED / "readiness_story_screen.gpkg").to_crs(WGS84)
    candidates_path = PROCESSED / "counterfactual_candidate_universe.gpkg"
    if not candidates_path.exists():
        raise FileNotFoundError("Run scripts/15_build_counterfactual_candidate_universe.py first")
    candidates = gpd.read_file(candidates_path).to_crs(WGS84)

    # Use zone representative points for network impedance.
    zones_points = zones.copy()
    zones_points["geometry"] = zones_points.to_crs(METRIC).representative_point().to_crs(WGS84)

    graph = load_graph()
    time_matrix = compute_time_matrix(graph, zones_points, candidates)
    time_df = pd.DataFrame(time_matrix, index=zones["zone_id"], columns=candidates["candidate_id"])
    time_df.to_csv(PROCESSED / "candidate_zone_network_minutes.csv")

    candidate_weight = (
        0.42 * candidates["activity_score"].fillna(0).to_numpy(dtype=float)
        + 0.34 * candidates["implementation_score"].fillna(0).to_numpy(dtype=float)
        + 0.24 * candidates["trap_exposure_score"].fillna(0).to_numpy(dtype=float)
    )
    raw_gain = np.exp(-time_matrix / DECAY_MIN) * candidate_weight[None, :]
    raw_gain[~np.isfinite(raw_gain)] = 0.0
    base_access = zones["access_screen"].fillna(0).to_numpy(dtype=float)
    base_d = disadvantage(base_access, zones)

    definitions = scenario_definitions(zones, candidates, base_d)
    selected_layers = []
    outcome_layers = []
    traces = []
    metric_rows = []
    for scenario_name, definition in definitions.items():
        selected, scenario_access, trace = run_greedy(
            definition, zones, candidates, raw_gain, base_access, BUDGET
        )
        scenario_d = disadvantage(scenario_access, zones)

        selected_gdf = candidates.iloc[selected].copy()
        selected_gdf["scenario"] = scenario_name
        selected_gdf["scenario_label"] = definition["label"]
        selected_gdf["rank"] = np.arange(1, len(selected_gdf) + 1)
        selected_layers.append(selected_gdf)

        outcome = zones.copy()
        outcome["scenario"] = scenario_name
        outcome["scenario_label"] = definition["label"]
        outcome["access_before"] = base_access
        outcome["access_after"] = scenario_access
        outcome["disadvantage_before"] = base_d
        outcome["disadvantage_after"] = scenario_d
        outcome["disadvantage_reduction"] = base_d - scenario_d
        outcome["initial_readiness_trap"] = base_d >= np.nanquantile(base_d, 0.75)
        outcome_layers.append(outcome)

        traces.extend([{**row, "scenario": scenario_name, "scenario_label": definition["label"]} for row in trace])
        metric_rows.append(
            metric_row(
                scenario_name,
                definition["label"],
                zones,
                candidates,
                selected,
                base_access,
                scenario_access,
                base_d,
                scenario_d,
            )
        )

    selected_all = pd.concat(selected_layers, ignore_index=True)
    selected_all = gpd.GeoDataFrame(selected_all, geometry="geometry", crs=WGS84)
    selected_all.to_file(PROCESSED / "counterfactual_selected_sites.gpkg", driver="GPKG")

    outcomes_all = pd.concat(outcome_layers, ignore_index=True)
    outcomes_all = gpd.GeoDataFrame(outcomes_all, geometry="geometry", crs=WGS84)
    outcomes_all.to_file(PROCESSED / "counterfactual_zone_outcomes.gpkg", driver="GPKG")

    metrics = pd.DataFrame(metric_rows).sort_values("mean_reduction", ascending=False)
    metrics.to_csv(TABLES / "table_counterfactual_scenarios.csv", index=False)
    compact = metrics[
        [
            "label",
            "mean_reduction",
            "top_quartile_mean_reduction",
            "trap_dissolution_rate",
            "spatial_leakage_index",
            "mean_selected_implementation",
        ]
    ].rename(
        columns={
            "label": "Expansion rule",
            "mean_reduction": "Mean gain",
            "top_quartile_mean_reduction": "Trap-zone gain",
            "trap_dissolution_rate": "Trap-zone exit",
            "spatial_leakage_index": "Leakage",
            "mean_selected_implementation": "Feasibility proxy",
        }
    )
    compact.to_latex(
        TABLES / "table_counterfactual_scenarios_compact.tex",
        index=False,
        float_format="%.3f",
        escape=False,
    )
    metrics.to_latex(
        TABLES / "table_counterfactual_scenarios.tex",
        index=False,
        float_format="%.3f",
        escape=False,
    )
    pd.DataFrame(traces).to_csv(TABLES / "table_counterfactual_selection_trace.csv", index=False)

    metadata = {
        "budget": BUDGET,
        "decay_min": DECAY_MIN,
        "gain_scale": GAIN_SCALE,
        "scenarios": {k: {"label": v["label"], "alpha": v["alpha"], "quality_weight": v["quality_weight"]} for k, v in definitions.items()},
        "interpretation": "Greedy territorial counterfactual for Cities narrative; not a deployment-ready optimization.",
    }
    (TABLES / "counterfactual_experiment_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote data_processed/counterfactual_selected_sites.gpkg")
    print(f"Wrote data_processed/counterfactual_zone_outcomes.gpkg")
    print(f"Wrote outputs/tables/table_counterfactual_scenarios.csv")


if __name__ == "__main__":
    main()
