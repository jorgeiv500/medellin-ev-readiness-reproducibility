from __future__ import annotations

import geopandas as gpd
import pandas as pd

from aaca_utils import ROOT, load_yaml


def main() -> None:
    params = load_yaml("config/parameters.yml")
    catalog = load_yaml("config/data_catalog.yml")
    crs_projected = params["project"]["crs_projected"]

    frames = []
    for name in ["osm_pois", "geomedellin"]:
        meta = catalog["sources"]["activity_anchors"].get(name)
        if not meta:
            continue
        path = ROOT / meta["path"]
        if path.exists() and path.suffix.lower() in {".gpkg", ".geojson", ".json", ".shp"}:
            gdf = gpd.read_file(path).to_crs(crs_projected)
            gdf["candidate_source"] = name
            frames.append(gdf)

    if not frames:
        print("No candidate source layers found yet. Add fuel stations, parking, commercial centers, facilities, and transit stations.")
        return

    candidates = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=crs_projected)
    chargers_path = ROOT / "data_processed/chargers_clean.gpkg"
    if chargers_path.exists():
        chargers = gpd.read_file(chargers_path).to_crs(crs_projected)
        exclusion = params["candidates"]["exclusion_existing_charger_m"]
        candidates = candidates[candidates.geometry.apply(lambda geom: chargers.distance(geom).min() > exclusion)]

    candidates["candidate_score"] = 0.0
    out = ROOT / "data_processed/candidate_sites.gpkg"
    candidates.to_file(out, driver="GPKG")
    print(f"Saved {len(candidates)} candidate sites to {out}")


if __name__ == "__main__":
    main()

