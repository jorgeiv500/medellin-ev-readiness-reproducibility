from __future__ import annotations

import geopandas as gpd

from aaca_utils import ROOT, palma_ratio, weighted_gini


def main() -> None:
    path = ROOT / "data_processed/aaca_scores.gpkg"
    if not path.exists():
        print("Missing data_processed/aaca_scores.gpkg. Run 06_compute_aaca.py first.")
        return

    gdf = gpd.read_file(path)
    weights = gdf["households"] if "households" in gdf.columns else None
    gini = weighted_gini(gdf["aaca_score"], weights)
    palma = palma_ratio(gdf["aaca_score"], weights)

    out = ROOT / "outputs/tables/equity_diagnostics.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"metric,value\nweighted_gini,{gini}\npalma,{palma}\n", encoding="utf-8")
    print(f"Saved {out}")
    print("Moran's I and LISA hooks should be added after spatial units have stable contiguity.")


if __name__ == "__main__":
    main()

