from __future__ import annotations

import geopandas as gpd

from aaca_utils import ROOT, load_yaml, minmax


def main() -> None:
    params = load_yaml("config/parameters.yml")
    units_path = ROOT / "data_processed/spatial_units.gpkg"
    if not units_path.exists():
        print("Missing data_processed/spatial_units.gpkg. Run or implement 01_prepare_boundaries.py first.")
        return

    units = gpd.read_file(units_path)
    weights = params["transition_need"]["weights"]
    required = {
        "ev_hybrid": "ev_hybrid",
        "private_motorized_trips": "private_motorized_trips",
        "home_charging_constraint": "home_charging_constraint",
        "auto_trips": "auto_trips",
        "vulnerability": "vulnerability",
    }

    for col in required.values():
        if col not in units.columns:
            print(f"Missing transition variable '{col}'. Filling with 0 until source is joined.")
            units[col] = 0.0

    units["transition_need"] = 0.0
    for key, col in required.items():
        units[f"{col}_norm"] = minmax(units[col])
        units["transition_need"] += weights[key] * units[f"{col}_norm"]

    out = ROOT / "data_processed/transition_need.gpkg"
    units.to_file(out, driver="GPKG")
    print(f"Saved transition need surface to {out}")


if __name__ == "__main__":
    main()

