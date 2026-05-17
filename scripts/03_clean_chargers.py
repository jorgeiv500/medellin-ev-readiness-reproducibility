from __future__ import annotations

import geopandas as gpd
import pandas as pd

from aaca_utils import ROOT, load_yaml, minmax


REQUIRED_COLUMNS = ["id", "nombre", "lat", "lon", "potencia_kw", "conectores", "operador", "estado", "fuente"]


def read_source(path: str, source_name: str) -> gpd.GeoDataFrame | None:
    full_path = ROOT / path
    if not full_path.exists():
        print(f"Skipping missing charger source {source_name}: {full_path}")
        return None

    if full_path.suffix.lower() in {".gpkg", ".geojson", ".json", ".shp"}:
        gdf = gpd.read_file(full_path)
    else:
        df = pd.read_csv(full_path)
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["lon"], df["lat"]),
            crs="EPSG:4326",
        )
    gdf["fuente"] = source_name
    return gdf


def main() -> None:
    params = load_yaml("config/parameters.yml")
    catalog = load_yaml("config/data_catalog.yml")
    charger_sources = catalog["sources"]["chargers"]
    frames = []

    for name, meta in charger_sources.items():
        frame = read_source(meta["path"], name)
        if frame is not None:
            frames.append(frame)

    if not frames:
        print("No charger sources found. Add files under data_raw/chargers and update config/data_catalog.yml.")
        return

    chargers = pd.concat(frames, ignore_index=True)
    chargers = gpd.GeoDataFrame(chargers, geometry="geometry", crs=frames[0].crs).to_crs(params["project"]["crs_projected"])

    priority = params["charger_cleaning"]["source_priority"]
    reliability = params["charger_cleaning"]["reliability"]
    chargers["source_priority"] = chargers["fuente"].map(priority).fillna(99)
    chargers["source_reliability"] = chargers["fuente"].map(reliability).fillna(0.50)
    chargers["capacity_proxy"] = chargers.get("conectores", 1).fillna(1).clip(lower=1)
    chargers["power_norm"] = minmax(chargers.get("potencia_kw", pd.Series(index=chargers.index, dtype=float)))

    chargers = chargers.sort_values(["source_priority", "power_norm"], ascending=[True, False])
    chargers["cluster_id"] = range(len(chargers))
    distance_m = params["charger_cleaning"]["duplicate_distance_m"]

    kept = []
    kept_union = gpd.GeoSeries([], crs=chargers.crs)
    for idx, row in chargers.iterrows():
        if kept_union.empty or kept_union.distance(row.geometry).min() > distance_m:
            kept.append(idx)
            kept_union = pd.concat([kept_union, gpd.GeoSeries([row.geometry], crs=chargers.crs)], ignore_index=True)

    clean = chargers.loc[kept].copy().to_crs(params["project"]["crs_geographic"])
    out = ROOT / "data_processed/chargers_clean.gpkg"
    clean.to_file(out, driver="GPKG")
    print(f"Saved {len(clean)} cleaned chargers to {out}")


if __name__ == "__main__":
    main()

