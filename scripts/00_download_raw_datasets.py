from __future__ import annotations

import csv
import gzip
import html
import json
import re
import shutil
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
import urllib3

from aaca_utils import ROOT


ACCESS_DATE = "2026-05-14"
HEADERS = {"User-Agent": "medellin-aaca-research/0.1"}
VALLE_MUNICIPALITIES = {
    5001: "Medellin",
    5079: "Barbosa",
    5088: "Bello",
    5129: "Caldas",
    5212: "Copacabana",
    5266: "Envigado",
    5308: "Girardota",
    5360: "Itagui",
    5380: "La Estrella",
    5631: "Sabaneta",
}
BBOX = {
    "south": 5.95,
    "west": -75.75,
    "north": 6.42,
    "east": -75.35,
}


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def request_get(url: str, *, verify: bool = True, params: dict[str, Any] | None = None, timeout: int = 90) -> requests.Response:
    response = requests.get(url, headers=HEADERS, params=params, timeout=timeout, verify=verify)
    response.raise_for_status()
    return response


def download_file(
    manifest: list[dict[str, Any]],
    label: str,
    url: str,
    path: str | Path,
    *,
    verify: bool = True,
    expected_magic: bytes | None = None,
) -> None:
    out = ROOT / Path(path)
    ensure_parent(out)
    try:
        response = request_get(url, verify=verify, timeout=180)
        out.write_bytes(response.content)
        if expected_magic and not response.content.startswith(expected_magic):
            raise ValueError(f"Unexpected file signature for {out}")
        manifest.append(
            {
                "status": "downloaded",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": url,
                "bytes": out.stat().st_size,
                "access_date": ACCESS_DATE,
                "notes": "",
            }
        )
        print(f"OK {label}: {out}")
    except Exception as exc:
        manifest.append(
            {
                "status": "failed",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": url,
                "bytes": "",
                "access_date": ACCESS_DATE,
                "notes": str(exc),
            }
        )
        print(f"FAILED {label}: {exc}")


def save_response_json(
    manifest: list[dict[str, Any]],
    label: str,
    url: str,
    path: str | Path,
    *,
    verify: bool = True,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any | None:
    out = ROOT / Path(path)
    ensure_parent(out)
    try:
        response = requests.get(url, headers=headers or HEADERS, params=params, timeout=120, verify=verify)
        response.raise_for_status()
        payload = response.json()
        write_json(out, payload)
        manifest.append(
            {
                "status": "downloaded",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": response.url,
                "bytes": out.stat().st_size,
                "access_date": ACCESS_DATE,
                "notes": "",
            }
        )
        print(f"OK {label}: {out}")
        return payload
    except Exception as exc:
        manifest.append(
            {
                "status": "failed",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": url,
                "bytes": "",
                "access_date": ACCESS_DATE,
                "notes": str(exc),
            }
        )
        print(f"FAILED {label}: {exc}")
        return None


def arcgis_count(layer_url: str, *, verify: bool = True) -> int | None:
    params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    try:
        response = request_get(f"{layer_url}/query", params=params, verify=verify, timeout=60)
        payload = response.json()
        return int(payload.get("count", 0))
    except Exception:
        return None


def arcgis_layer_geojson(
    manifest: list[dict[str, Any]],
    label: str,
    layer_url: str,
    path: str | Path,
    *,
    verify: bool = True,
    batch_size: int = 1000,
) -> None:
    out = ROOT / Path(path)
    ensure_parent(out)
    features: list[dict[str, Any]] = []
    count = arcgis_count(layer_url, verify=verify)
    try:
        if count is None or count == 0:
            count = batch_size
        for offset in range(0, count, batch_size):
            params = {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
            }
            response = request_get(f"{layer_url}/query", params=params, verify=verify, timeout=120)
            payload = response.json()
            page = payload.get("features", [])
            features.extend(page)
            if len(page) < batch_size:
                break
            time.sleep(0.2)
        collection = {"type": "FeatureCollection", "features": features}
        write_json(out, collection)
        manifest.append(
            {
                "status": "downloaded",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": layer_url,
                "bytes": out.stat().st_size,
                "access_date": ACCESS_DATE,
                "notes": f"{len(features)} features",
            }
        )
        print(f"OK {label}: {len(features)} features")
    except Exception as exc:
        manifest.append(
            {
                "status": "failed",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": layer_url,
                "bytes": "",
                "access_date": ACCESS_DATE,
                "notes": str(exc),
            }
        )
        print(f"FAILED {label}: {exc}")


def arcgis_json_by_ids(
    manifest: list[dict[str, Any]],
    label: str,
    layer_url: str,
    path: str | Path,
    *,
    verify: bool = True,
    batch_size: int = 250,
) -> None:
    out = ROOT / Path(path)
    ensure_parent(out)
    try:
        ids_resp = request_get(
            f"{layer_url}/query",
            params={"where": "1=1", "returnIdsOnly": "true", "f": "json"},
            verify=verify,
            timeout=120,
        )
        ids_payload = ids_resp.json()
        object_ids = ids_payload.get("objectIds", [])
        features: list[dict[str, Any]] = []
        fields: list[dict[str, Any]] | None = None
        for i in range(0, len(object_ids), batch_size):
            batch = object_ids[i : i + batch_size]
            params = {
                "objectIds": ",".join(str(x) for x in batch),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "json",
            }
            response = request_get(f"{layer_url}/query", params=params, verify=verify, timeout=120)
            payload = response.json()
            fields = fields or payload.get("fields")
            features.extend(payload.get("features", []))
            time.sleep(0.2)
        write_json(
            out,
            {
                "type": "ArcGISFeatureSet",
                "source": layer_url,
                "objectIdFieldName": ids_payload.get("objectIdFieldName", "OBJECTID"),
                "fields": fields,
                "features": features,
            },
        )
        manifest.append(
            {
                "status": "downloaded",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": layer_url,
                "bytes": out.stat().st_size,
                "access_date": ACCESS_DATE,
                "notes": f"{len(features)} features by objectIds",
            }
        )
        print(f"OK {label}: {len(features)} features")
    except Exception as exc:
        manifest.append(
            {
                "status": "failed",
                "label": label,
                "path": str(path).replace("\\", "/"),
                "url": layer_url,
                "bytes": "",
                "access_date": ACCESS_DATE,
                "notes": str(exc),
            }
        )
        print(f"FAILED {label}: {exc}")


def download_cargame(manifest: list[dict[str, Any]]) -> None:
    token = (
        "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
        "eyJpZCI6MCwidXN1YXJpbyI6InBvd2VyYmkiLCJyb2xlIjoiaW50ZWxsaWdlbmNlIiwiaWF0IjoxNTk0ODQ5NjMxfQ."
        "UY3BLtqi5zdxpRFaT9XIsYvQIV4gPPXN6iO39AlymMY"
    )
    headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "authorization": token,
        "Origin": "https://cargame.minenergia.gov.co",
        "Referer": "https://cargame.minenergia.gov.co/",
    }
    url = "https://siveeic.minenergia.gov.co:3011/crg/resumenestacionescarga/0/0"
    payload = save_response_json(
        manifest,
        "CargaME national charging-station registry",
        url,
        "data_raw/chargers/cargame_national_raw.json",
        verify=False,
        headers=headers,
    )
    if not isinstance(payload, list):
        return
    valle = []
    for record in payload:
        municipio = record.get("Municipio") or {}
        mid = municipio.get("Id")
        try:
            mid_int = int(mid)
        except Exception:
            continue
        if mid_int in VALLE_MUNICIPALITIES:
            valle.append(record)
    write_json(ROOT / "data_raw/chargers/cargame_valle_aburra_raw.json", valle)
    features = []
    for record in valle:
        try:
            lat = float(str(record.get("Latitud")).replace(",", "."))
            lon = float(str(record.get("Longitud")).replace(",", "."))
        except Exception:
            continue
        props = dict(record)
        props.pop("Latitud", None)
        props.pop("Longitud", None)
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props})
    write_json(
        ROOT / "data_raw/chargers/cargame_valle_aburra.geojson",
        {"type": "FeatureCollection", "features": features},
    )
    manifest.append(
        {
            "status": "generated",
            "label": "CargaME Valle de Aburra subset",
            "path": "data_raw/chargers/cargame_valle_aburra.geojson",
            "url": url,
            "bytes": (ROOT / "data_raw/chargers/cargame_valle_aburra.geojson").stat().st_size,
            "access_date": ACCESS_DATE,
            "notes": f"{len(features)} point features from {len(valle)} raw records",
        }
    )
    print(f"OK CargaME Valle de Aburra subset: {len(features)} features")


def download_epm_socrata(manifest: list[dict[str, Any]]) -> None:
    datasets = [
        (
            "EPM public charging use records 2019-2025",
            "bff2-84yc",
            "data_raw/chargers/epm_public_charging_use_2019_2025.csv",
        ),
        (
            "EPM CNG and public EV charging stations",
            "qqm3-dw2u",
            "data_raw/chargers/epm_gnv_ev_stations.csv",
        ),
    ]
    for label, dataset_id, out_csv in datasets:
        download_file(
            manifest,
            label,
            f"https://www.datos.gov.co/resource/{dataset_id}.csv?$limit=500000",
            out_csv,
        )
        save_response_json(
            manifest,
            f"{label} metadata",
            f"https://www.datos.gov.co/api/views/{dataset_id}",
            f"data_raw/chargers/metadata_{dataset_id}.json",
        )


def download_amva_eod(manifest: list[dict[str, Any]]) -> None:
    base = "https://datosabiertos.metropol.gov.co/sites/default/files/uploaded_resources"
    files = [
        ("AMVA EOD 2017 households", "EOD_2017_DatosHogares.csv", "data_raw/mobility/eod_valle_aburra/EOD_2017_DatosHogares.csv"),
        ("AMVA EOD 2017 residents", "EOD_2017_DatosMoradores_0.csv", "data_raw/mobility/eod_valle_aburra/EOD_2017_DatosMoradores_0.csv"),
        ("AMVA EOD 2017 trips", "EOD_2017_DatosViajes_1_0.csv", "data_raw/mobility/eod_valle_aburra/EOD_2017_DatosViajes_1_0.csv"),
        (
            "AMVA SIT macrozones and zones shapefile",
            "Zonificaci%C3%B3n%20Macrozonas%20y%20zonas%20SIT%20en%20formato%20SHP.zip",
            "data_raw/boundaries/amva/zonificacion_macrozona_zonas_sit_shp.zip",
        ),
    ]
    for label, remote, out in files:
        download_file(manifest, label, f"{base}/{remote}", out, verify=False)


def download_gtfs(manifest: list[dict[str, Any]]) -> None:
    api = "https://api.github.com/repos/ColombiaInfo/ColombiaGTFS/contents/Medellin%20-%20Metro"
    payload = save_response_json(
        manifest,
        "ColombiaGTFS Medellin Metro directory listing",
        api,
        "data_raw/gtfs/metro_medellin/github_directory_listing.json",
    )
    if not isinstance(payload, list):
        return
    for item in payload:
        name = item.get("name")
        download_url = item.get("download_url")
        if name and download_url and name.endswith((".txt", ".md")):
            download_file(manifest, f"GTFS Metro Medellin {name}", download_url, f"data_raw/gtfs/metro_medellin/{name}")


def download_medellin_projection_workbooks(manifest: list[dict[str, Any]]) -> None:
    page = "https://www.medellin.gov.co/es/centro-documental/proyecciones-poblacion-viviendas-y-hogares/"
    response = request_get(page, timeout=60)
    links = re.findall(r'href="([^"]+)"[^>]*>([^<]+)', response.text)
    targets = []
    wanted = ["Comunas", "Barrios", "Hogares", "Viviendas", "Deficit", "Déficit"]
    for href, text in links:
        plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
        if not href.lower().endswith((".xlsx", ".xls")) and ".xlsx" not in href.lower():
            continue
        if any(w in plain for w in wanted):
            url = urllib.parse.urljoin(page, href)
            name = re.sub(r"[^A-Za-z0-9_.-]+", "_", urllib.parse.unquote(url.split("/")[-1]))
            targets.append((text.strip(), url, f"data_raw/demographics/medellin/{name}"))
    seen: set[str] = set()
    for label, url, out in targets:
        if url in seen:
            continue
        seen.add(url)
        download_file(manifest, f"Medellin demographic workbook: {plain.strip()}", url, out, expected_magic=b"PK")


def download_overpass(manifest: list[dict[str, Any]]) -> None:
    overpass_url = "https://overpass-api.de/api/interpreter"
    bbox = f'{BBOX["south"]},{BBOX["west"]},{BBOX["north"]},{BBOX["east"]}'
    queries = [
        (
            "OSM EV charging stations Valle de Aburra bbox",
            "data_raw/osm/overpass_charging_stations.json",
            f"""
            [out:json][timeout:180];
            (
              node["amenity"="charging_station"]({bbox});
              way["amenity"="charging_station"]({bbox});
              relation["amenity"="charging_station"]({bbox});
            );
            out center tags;
            """,
        ),
        (
            "OSM fuel stations Valle de Aburra bbox",
            "data_raw/osm/overpass_fuel_stations.json",
            f"""
            [out:json][timeout:180];
            (
              node["amenity"="fuel"]({bbox});
              way["amenity"="fuel"]({bbox});
              relation["amenity"="fuel"]({bbox});
            );
            out center tags;
            """,
        ),
        (
            "OSM parking Valle de Aburra bbox",
            "data_raw/osm/overpass_parking.json",
            f"""
            [out:json][timeout:180];
            (
              node["amenity"="parking"]({bbox});
              way["amenity"="parking"]({bbox});
              relation["amenity"="parking"]({bbox});
            );
            out center tags;
            """,
        ),
        (
            "OSM activity anchors Valle de Aburra bbox",
            "data_raw/osm/overpass_activity_anchors.json",
            f"""
            [out:json][timeout:180];
            (
              node["amenity"~"hospital|clinic|university|school|library|arts_centre|theatre|cinema"]({bbox});
              way["amenity"~"hospital|clinic|university|school|library|arts_centre|theatre|cinema"]({bbox});
              relation["amenity"~"hospital|clinic|university|school|library|arts_centre|theatre|cinema"]({bbox});
              node["shop"~"mall|supermarket|department_store"]({bbox});
              way["shop"~"mall|supermarket|department_store"]({bbox});
              relation["shop"~"mall|supermarket|department_store"]({bbox});
            );
            out center tags;
            """,
        ),
    ]
    for label, out, query in queries:
        try:
            response = requests.post(overpass_url, data={"data": query}, headers=HEADERS, timeout=240)
            response.raise_for_status()
            payload = response.json()
            write_json(ROOT / out, payload)
            manifest.append(
                {
                    "status": "downloaded",
                    "label": label,
                    "path": out,
                    "url": overpass_url,
                    "bytes": (ROOT / out).stat().st_size,
                    "access_date": ACCESS_DATE,
                    "notes": f"{len(payload.get('elements', []))} OSM elements",
                }
            )
            print(f"OK {label}: {len(payload.get('elements', []))} elements")
        except Exception as exc:
            manifest.append(
                {
                    "status": "failed",
                    "label": label,
                    "path": out,
                    "url": overpass_url,
                    "bytes": "",
                    "access_date": ACCESS_DATE,
                    "notes": str(exc),
                }
            )
            print(f"FAILED {label}: {exc}")


def download_arcgis_layers(manifest: list[dict[str, Any]]) -> None:
    base = "https://www.medellin.gov.co/servidormapas/rest/services"
    layers = [
        ("GeoMedellin transit stops", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/0", "data_raw/transport/geomedellin/transit_stops.geojson"),
        ("GeoMedellin cycloroutes", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/1", "data_raw/transport/geomedellin/cycloroutes.geojson"),
        ("GeoMedellin road hierarchy", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/2", "data_raw/transport/geomedellin/road_hierarchy.geojson"),
        ("GeoMedellin passenger transport corridors", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/6", "data_raw/transport/geomedellin/passenger_transport_corridors.geojson"),
        ("GeoMedellin mass transport stations", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/11", "data_raw/transport/geomedellin/mass_transport_stations.geojson"),
        ("GeoMedellin mass transport lines", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/12", "data_raw/transport/geomedellin/mass_transport_lines.geojson"),
        ("GeoMedellin cycling network", f"{base}/transporte/VC_Infraest_Gestion_Transporte/MapServer/13", "data_raw/transport/geomedellin/cycling_network.geojson"),
        ("GeoMedellin land classification", f"{base}/ordenamiento_ter/VM_02_Clasificacion_Suelo/MapServer/4", "data_raw/planning/geomedellin/land_classification.geojson"),
        ("GeoMedellin collective facilities categories", f"{base}/ordenamiento_ter/VM_13_Subsistema_Equipamientos_Colectivos/MapServer/2", "data_raw/planning/geomedellin/collective_facilities_categories.geojson"),
        ("GeoMedellin urban road hierarchy POT", f"{base}/ordenamiento_ter/VM_16_Subs_Movilidad/MapServer/2", "data_raw/planning/geomedellin/pot_urban_road_hierarchy.geojson"),
        ("GeoMedellin POT passenger transport corridors", f"{base}/ordenamiento_ter/VM_16_Subs_Movilidad/MapServer/3", "data_raw/planning/geomedellin/pot_passenger_transport_corridors.geojson"),
        ("GeoMedellin centralities", f"{base}/ordenamiento_ter/VM_20_Subs_Centralidades/MapServer/1", "data_raw/planning/geomedellin/centralities.geojson"),
        ("GeoMedellin POT cycloroutes", f"{base}/ordenamiento_ter/VM_20_Subs_Centralidades/MapServer/3", "data_raw/planning/geomedellin/pot_cycloroutes.geojson"),
        ("GeoMedellin urban land use", f"{base}/ordenamiento_ter/VM_23_Uso_General_Suelo_Urbano/MapServer/2", "data_raw/planning/geomedellin/urban_land_use.geojson"),
        ("GeoMedellin higher education institutions", f"{base}/educacion/VC_Sedes/MapServer/1", "data_raw/activity/geomedellin/higher_education_institutions.geojson"),
        ("GeoMedellin education sites", f"{base}/educacion/VC_Sedes/MapServer/0", "data_raw/activity/geomedellin/education_sites.geojson"),
        ("GeoMedellin ECV food insecurity", f"{base}/estadisticas/VC_Indicadores_ECV/MapServer/0", "data_raw/demographics/medellin_arcgis/ecv_food_insecurity.geojson"),
        ("GeoMedellin ECV multidimensional poverty", f"{base}/estadisticas/VC_Indicadores_ECV/MapServer/1", "data_raw/demographics/medellin_arcgis/ecv_multidimensional_poverty.geojson"),
        ("GeoMedellin ECV IMCV", f"{base}/estadisticas/VC_Indicadores_ECV/MapServer/2", "data_raw/demographics/medellin_arcgis/ecv_imcv.geojson"),
        ("GeoMedellin ECV HDI", f"{base}/estadisticas/VC_Indicadores_ECV/MapServer/3", "data_raw/demographics/medellin_arcgis/ecv_hdi.geojson"),
        ("GeoMedellin ECV unemployment", f"{base}/estadisticas/VC_Indicadores_ECV/MapServer/4", "data_raw/demographics/medellin_arcgis/ecv_unemployment.geojson"),
        ("GeoMedellin population projection by comuna", f"{base}/mapas_nacionales/VC_Distribucion_Poblacional/MapServer/1", "data_raw/demographics/medellin_arcgis/population_projection_comuna.geojson"),
        ("GeoMedellin households projection by comuna", f"{base}/mapas_nacionales/VC_Distribucion_Poblacional/MapServer/2", "data_raw/demographics/medellin_arcgis/households_projection_comuna.geojson"),
        ("GeoMedellin dwellings projection by comuna", f"{base}/mapas_nacionales/VC_Distribucion_Poblacional/MapServer/3", "data_raw/demographics/medellin_arcgis/dwellings_projection_comuna.geojson"),
        ("GeoMedellin traffic incidents 2022 total", f"{base}/transporte/VM_Accidentes/MapServer/32", "data_raw/safety/geomedellin/traffic_incidents_2022_total.geojson"),
        ("GeoMedellin traffic deaths 2022", f"{base}/transporte/VM_Accidentes/MapServer/33", "data_raw/safety/geomedellin/traffic_deaths_2022.geojson"),
        ("GeoMedellin traffic injuries 2022", f"{base}/transporte/VM_Accidentes/MapServer/34", "data_raw/safety/geomedellin/traffic_injuries_2022.geojson"),
    ]
    for label, url, out in layers:
        arcgis_layer_geojson(manifest, label, url, out, verify=True)


def download_medellin_stratum_attributes(manifest: list[dict[str, Any]]) -> None:
    layer_url = "https://www.medellin.gov.co/servidormapas/rest/services/mapas_nacionales/VC_Distribucion_Poblacional/MapServer/0"
    out_json = ROOT / "data_raw/demographics/medellin_arcgis/socioeconomic_stratum_attributes.json"
    out_csv = ROOT / "data_raw/demographics/medellin_arcgis/socioeconomic_stratum_attributes.csv"
    ensure_parent(out_json)
    try:
        ids_payload = request_get(
            f"{layer_url}/query",
            params={"where": "1=1", "returnIdsOnly": "true", "f": "json"},
            timeout=90,
        ).json()
        object_ids = ids_payload["objectIds"]
        fields: list[dict[str, Any]] | None = None
        records: list[dict[str, Any]] = []
        for i in range(0, len(object_ids), 500):
            batch = object_ids[i : i + 500]
            payload = request_get(
                f"{layer_url}/query",
                params={
                    "objectIds": ",".join(str(x) for x in batch),
                    "outFields": "*",
                    "returnGeometry": "false",
                    "f": "json",
                },
                timeout=120,
            ).json()
            fields = fields or payload.get("fields")
            records.extend(feature["attributes"] for feature in payload.get("features", []))
            time.sleep(0.05)
        write_json(out_json, {"source": layer_url, "fields": fields, "records": records})
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            if records:
                writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
                writer.writeheader()
                writer.writerows(records)
        for status, label, out in [
            ("downloaded", "GeoMedellin socioeconomic stratum attributes JSON", out_json),
            ("generated", "GeoMedellin socioeconomic stratum attributes CSV", out_csv),
        ]:
            manifest.append(
                {
                    "status": status,
                    "label": label,
                    "path": str(out.relative_to(ROOT)).replace("\\", "/"),
                    "url": layer_url,
                    "bytes": out.stat().st_size,
                    "access_date": ACCESS_DATE,
                    "notes": f"{len(records)} records; geometry omitted because block polygons are very large",
                }
            )
        print(f"OK GeoMedellin socioeconomic stratum attributes: {len(records)} records")
    except Exception as exc:
        manifest.append(
            {
                "status": "failed",
                "label": "GeoMedellin socioeconomic stratum attributes",
                "path": "data_raw/demographics/medellin_arcgis/socioeconomic_stratum_attributes.csv",
                "url": layer_url,
                "bytes": "",
                "access_date": ACCESS_DATE,
                "notes": str(exc),
            }
        )
        print(f"FAILED GeoMedellin socioeconomic stratum attributes: {exc}")


def download_upme_substations(manifest: list[dict[str, Any]]) -> None:
    layer_url = "https://geo.upme.gov.co/server/rest/services/SUBESTACIONES/UPME_EN_DI_SUBESTACION_edicion/FeatureServer/0"
    arcgis_json_by_ids(
        manifest,
        "UPME distribution substations national layer",
        layer_url,
        "data_raw/electric/upme_substations_national_raw.json",
        verify=False,
    )


def download_dem(manifest: list[dict[str, Any]]) -> None:
    tiles = [
        ("SRTM/Skadi DEM N05W076", "https://s3.amazonaws.com/elevation-tiles-prod/skadi/N05/N05W076.hgt.gz", "data_raw/topography/N05W076.hgt.gz"),
        ("SRTM/Skadi DEM N06W076", "https://s3.amazonaws.com/elevation-tiles-prod/skadi/N06/N06W076.hgt.gz", "data_raw/topography/N06W076.hgt.gz"),
    ]
    for label, url, out in tiles:
        download_file(manifest, label, url, out, expected_magic=b"\x1f\x8b")
        gz_path = ROOT / out
        if gz_path.exists():
            hgt_path = gz_path.with_suffix("")
            try:
                with gzip.open(gz_path, "rb") as src, open(hgt_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                manifest.append(
                    {
                        "status": "generated",
                        "label": f"{label} decompressed HGT",
                        "path": str(hgt_path.relative_to(ROOT)).replace("\\", "/"),
                        "url": url,
                        "bytes": hgt_path.stat().st_size,
                        "access_date": ACCESS_DATE,
                        "notes": "",
                    }
                )
                print(f"OK {label} decompressed: {hgt_path}")
            except Exception as exc:
                print(f"FAILED decompress {label}: {exc}")


def write_manifest(manifest: list[dict[str, Any]]) -> None:
    out = ROOT / "data_raw/raw_dataset_manifest.csv"
    ensure_parent(out)
    fields = ["status", "label", "path", "url", "bytes", "access_date", "notes"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
    print(f"Manifest saved: {out}")


def main() -> None:
    manifest: list[dict[str, Any]] = []
    download_cargame(manifest)
    download_epm_socrata(manifest)
    download_amva_eod(manifest)
    download_gtfs(manifest)
    download_medellin_projection_workbooks(manifest)
    download_overpass(manifest)
    download_arcgis_layers(manifest)
    download_medellin_stratum_attributes(manifest)
    download_upme_substations(manifest)
    download_dem(manifest)

    manifest.append(
        {
            "status": "blocked",
            "label": "OpenChargeMap Medellin/Valle de Aburra export",
            "path": "data_raw/chargers/openchargemap_medellin.geojson",
            "url": "https://api.openchargemap.io/v3/poi/",
            "bytes": "",
            "access_date": ACCESS_DATE,
            "notes": "API returned 403 without an API key; provide OPENCHARGEMAP_API_KEY for a later authenticated run.",
        }
    )
    write_manifest(manifest)


if __name__ == "__main__":
    main()
