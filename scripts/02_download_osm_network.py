from __future__ import annotations

import osmnx as ox
import osmnx._http as ox_http

from aaca_utils import ROOT, load_yaml


def main() -> None:
    params = load_yaml("config/parameters.yml")
    network_cfg = params["network"]
    out = ROOT / "data_processed/road_network.graphml"

    place = params["project"]["study_area_name"]
    print(f"Downloading OSM drive network for: {place}")
    # OSMnx 2.0.6 can conflict with urllib3-future's getaddrinfo signature
    # in this local environment. Disabling DNS pinning keeps Overpass usable.
    ox_http._config_dns = lambda url: None
    ox.settings.overpass_settings = "[out:json][timeout:180]"
    try:
        graph = ox.graph_from_place(place, network_type=network_cfg["network_type"], simplify=True)
    except Exception as exc:
        print(f"Place download failed ({exc}); falling back to Valle de Aburra bbox.")
        bbox = (-75.75, 5.95, -75.35, 6.42)
        graph = ox.graph_from_bbox(bbox, network_type=network_cfg["network_type"], simplify=True)
    graph = ox.add_edge_speeds(graph, hwy_speeds=network_cfg["speed_by_highway"], fallback=network_cfg["default_speed_kph"])
    graph = ox.add_edge_travel_times(graph)
    ox.save_graphml(graph, out)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
