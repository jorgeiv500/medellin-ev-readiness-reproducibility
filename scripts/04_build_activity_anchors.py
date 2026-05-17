from __future__ import annotations

import geopandas as gpd
import pandas as pd

from aaca_utils import ROOT, load_yaml


def main() -> None:
    params = load_yaml("config/parameters.yml")
    catalog = load_yaml("config/data_catalog.yml")
    crs_projected = params["project"]["crs_projected"]

    candidates = []
    for group, meta in catalog["sources"]["activity_anchors"].items():
        path = ROOT / meta["path"]
        if path.exists() and path.suffix.lower() in {".gpkg", ".geojson", ".json", ".shp"}:
            gdf = gpd.read_file(path).to_crs(crs_projected)
            gdf["anchor_type"] = group
            candidates.append(gdf[["anchor_type", "geometry"]])
        else:
            print(f"Missing or non-spatial activity source: {group} ({path})")

    gtfs_path = ROOT / catalog["sources"]["transport"]["gtfs_sitva"]["path"]
    print(f"GTFS parsing is pending. Expected source folder: {gtfs_path}")

    if not candidates:
        print("No activity-anchor layers found yet.")
        return

    anchors = gpd.GeoDataFrame(pd.concat(candidates, ignore_index=True), crs=crs_projected)
    out = ROOT / "data_processed/activity_anchors.gpkg"
    anchors.to_file(out, driver="GPKG")
    print(f"Saved {len(anchors)} anchors to {out}")


if __name__ == "__main__":
    main()

