from __future__ import annotations

import importlib

from aaca_utils import ROOT, ensure_dirs, load_yaml


REQUIRED = [
    "geopandas",
    "pandas",
    "numpy",
    "scipy",
    "shapely",
    "osmnx",
    "networkx",
    "libpysal",
    "esda",
    "folium",
    "yaml",
]


def main() -> None:
    ensure_dirs([
        "data_raw",
        "data_processed",
        "outputs/figures",
        "outputs/tables",
        "outputs/maps",
        "paper",
    ])
    params = load_yaml("config/parameters.yml")
    missing = []
    for package in REQUIRED:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)

    if missing:
        raise SystemExit(f"Missing Python packages: {', '.join(missing)}")

    print(f"Environment OK for {params['project']['name']}")
    print(f"Project root: {ROOT}")


if __name__ == "__main__":
    main()

