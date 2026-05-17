from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from aaca_utils import ROOT, load_yaml


def main() -> None:
    params = load_yaml("config/parameters.yml")
    catalog = load_yaml("config/data_catalog.yml")
    preferred = params["spatial_units"]["preferred"]

    print(f"Preferred spatial units: {preferred}")
    print("Add OD-zone, barrio/section, or H3 boundary generation here.")
    print("Expected output: data_processed/spatial_units.gpkg")
    print(f"Catalog mobility path: {catalog['sources']['mobility']['eod_valle_aburra']['path']}")

    out = ROOT / "data_processed/spatial_units.gpkg"
    if out.exists():
        gdf = gpd.read_file(out)
        print(f"Existing spatial units found: {len(gdf)} features")
    else:
        print("No spatial_units.gpkg found yet.")


if __name__ == "__main__":
    main()

