"""
Download and normalize recent Metro de Medellin passenger-flow evidence.

The AACA draft already uses the 2017 OD survey for household/trip structure.
This enrichment adds a more recent activity-pressure layer from the open Metro
ArcGIS Hub catalog. The output is intentionally conservative: it characterizes
system-level and line-level temporal patterns, but it does not fabricate
station-level demand where the public file does not expose it.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data_raw" / "mobility" / "metro_afluencia"
PROCESSED_DIR = ROOT / "data_processed"
TABLE_DIR = ROOT / "outputs" / "tables"

HUB_SEARCH_URL = (
    "https://datosabiertos-metrodemedellin.opendata.arcgis.com/"
    "api/search/v1/collections/all/items"
)
ARCGIS_ITEM_URL = "https://www.arcgis.com/sharing/rest/content/items/{item_id}"
ARCGIS_DATA_URL = "https://www.arcgis.com/sharing/rest/content/items/{item_id}/data"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^0-9a-zA-Z]+", "_", value).strip("_").lower()
    return value or "unnamed"


def norm_col(value: str) -> str:
    return slugify(value)


def infer_year(*values: str) -> int | None:
    text = " ".join(str(v) for v in values if v)
    match = re.search(r"(20[0-3][0-9])", text)
    return int(match.group(1)) if match else None


def search_afluencia_items() -> list[dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    params = {"q": "Afluencia", "limit": 50}
    response = requests.get(HUB_SEARCH_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    (RAW_DIR / "metro_afluencia_hub_search.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    raw_items = []
    if payload.get("data"):
        raw_items.extend(payload.get("data", []))
    if payload.get("features"):
        raw_items.extend(payload.get("features", []))

    items = []
    for item in raw_items:
        attributes = item.get("attributes") or item.get("properties") or {}
        title = attributes.get("name") or attributes.get("title") or ""
        item_id = item.get("id") or attributes.get("id")
        if not item_id:
            continue
        text = " ".join(
            [
                title,
                attributes.get("description") or "",
                attributes.get("snippet") or "",
                attributes.get("type") or "",
            ]
        ).lower()
        if "afluencia" not in text:
            continue
        if not any(token in text for token in ["xlsx", "excel", "microsoft excel"]):
            continue
        items.append(
            {
                "item_id": item_id,
                "title": title,
                "year": infer_year(title, attributes.get("description") or ""),
                "source_url": ARCGIS_DATA_URL.format(item_id=item_id),
            }
        )

    # Keep one item per title/id and prefer dated files over the generic
    # "Afluencia_Metro" workbook if both point to the same year later.
    seen = set()
    unique = []
    for item in sorted(items, key=lambda x: (x["year"] is None, x["year"] or 0, x["title"])):
        key = (item["item_id"], item["title"])
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique


def download_item(item: dict) -> Path | None:
    item_id = item["item_id"]
    meta_url = ARCGIS_ITEM_URL.format(item_id=item_id)
    meta = requests.get(meta_url, params={"f": "json"}, timeout=60)
    if meta.ok:
        (RAW_DIR / f"{item_id}_metadata.json").write_text(
            json.dumps(meta.json(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    out_name = f"{item.get('year') or 'undated'}_{slugify(item['title'])}_{item_id}.xlsx"
    out_path = RAW_DIR / out_name
    if out_path.exists() and out_path.stat().st_size > 1000:
        return out_path

    response = requests.get(item["source_url"], timeout=120)
    if not response.ok or len(response.content) < 1000:
        return None
    out_path.write_bytes(response.content)
    return out_path


def choose_value_col(df: pd.DataFrame) -> str | None:
    priority_tokens = ["afluencia", "viajero", "pasajero", "cantidad", "conteo", "total"]
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    for token in priority_tokens:
        matches = [c for c in numeric_cols if token in c]
        if matches:
            return matches[0]
    if numeric_cols:
        return numeric_cols[-1]
    return None


def first_matching(columns: Iterable[str], tokens: Iterable[str]) -> str | None:
    for token in tokens:
        for col in columns:
            if token in col:
                return col
    return None


def parse_excel_dates(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    parsed = pd.to_datetime(values, errors="coerce")
    numeric_mask = parsed.isna() & numeric.notna()
    if numeric_mask.any():
        parsed.loc[numeric_mask] = pd.to_datetime(
            numeric.loc[numeric_mask], unit="D", origin="1899-12-30", errors="coerce"
        )
    return parsed


def normalize_pivot_sheet(raw: pd.DataFrame, sheet_name: str, path: Path, fallback_year: int | None) -> pd.DataFrame:
    day_row = None
    for idx, row in raw.iterrows():
        tokens = [norm_col(v) for v in row.tolist()]
        if "dia" in tokens and any("linea" in token for token in tokens):
            day_row = idx
            break
    if day_row is None or day_row + 1 >= len(raw):
        return pd.DataFrame()

    hour_row = day_row + 1
    data = raw.iloc[day_row + 2 :].copy()
    data = data.dropna(how="all")
    if data.empty:
        return pd.DataFrame()

    records = []
    dates = parse_excel_dates(data.iloc[:, 0])
    lines = data.iloc[:, 1].astype(str).str.strip().str.upper()
    for col_idx in range(2, raw.shape[1]):
        header_token = norm_col(raw.iloc[day_row, col_idx])
        hour_value = raw.iloc[hour_row, col_idx]
        hour_token = norm_col(hour_value)
        is_total = "total" in header_token or "total" in hour_token
        if pd.isna(hour_value) and not is_total:
            continue
        values = pd.to_numeric(data.iloc[:, col_idx], errors="coerce")
        if values.notna().sum() == 0:
            continue
        hour_text = "total" if is_total else str(hour_value)
        records.append(
            pd.DataFrame(
                {
                    "source_file": path.name,
                    "sheet": sheet_name,
                    "year": fallback_year,
                    "line": lines,
                    "date": dates,
                    "hour": hour_text,
                    "station": pd.NA,
                    "flow_kind": "daily_line_total" if is_total else "line_hour",
                    "passenger_flow": values,
                }
            )
        )
    if not records:
        return pd.DataFrame()
    out = pd.concat(records, ignore_index=True)
    out = out[out["passenger_flow"].notna()]
    if fallback_year is None and out["date"].notna().any():
        out["year"] = out["date"].dt.year
    return out


def normalize_workbook(path: Path, fallback_year: int | None) -> pd.DataFrame:
    records = []
    try:
        raw_sheets = pd.read_excel(path, sheet_name=None, header=None)
    except Exception as exc:  # pragma: no cover - defensive against corrupt web files
        return pd.DataFrame(
            [{"source_file": path.name, "parse_status": f"failed: {exc}", "year": fallback_year}]
        )

    for sheet_name, raw in raw_sheets.items():
        if raw.empty:
            continue
        pivot = normalize_pivot_sheet(raw, sheet_name, path, fallback_year)
        if not pivot.empty:
            records.append(pivot)
            continue

        df = raw.copy()
        df.columns = [norm_col(c) for c in df.columns]
        df = df.dropna(how="all")
        if len(df) == 0:
            continue

        value_col = choose_value_col(df)
        if not value_col:
            continue

        line_col = first_matching(df.columns, ["linea", "line"])
        date_col = first_matching(df.columns, ["fecha", "dia"])
        hour_col = first_matching(df.columns, ["hora", "franja"])
        station_col = first_matching(df.columns, ["estacion", "parada"])

        keep = {
            "source_file": path.name,
            "sheet": sheet_name,
            "year": fallback_year,
            "line": df[line_col].astype(str) if line_col else pd.NA,
            "date": df[date_col] if date_col else pd.NA,
            "hour": df[hour_col] if hour_col else pd.NA,
            "station": df[station_col].astype(str) if station_col else pd.NA,
            "flow_kind": "unknown",
            "passenger_flow": pd.to_numeric(df[value_col], errors="coerce"),
        }
        normalized = pd.DataFrame(keep)
        normalized = normalized[normalized["passenger_flow"].notna()]
        records.append(normalized)

    if not records:
        return pd.DataFrame(
            [{"source_file": path.name, "parse_status": "no tabular passenger-flow sheet", "year": fallback_year}]
        )
    return pd.concat(records, ignore_index=True)


def summarize(long_df: pd.DataFrame) -> pd.DataFrame:
    if "passenger_flow" not in long_df.columns:
        return pd.DataFrame()
    usable = long_df[long_df["passenger_flow"].notna()].copy()
    if usable.empty:
        return pd.DataFrame()
    if "flow_kind" in usable.columns and usable["flow_kind"].eq("daily_line_total").any():
        usable = usable[usable["flow_kind"].eq("daily_line_total")].copy()
    usable["year"] = pd.to_numeric(usable["year"], errors="coerce").astype("Int64")
    by_year = (
        usable.groupby("year", dropna=False)
        .agg(
            records=("passenger_flow", "size"),
            total_passenger_flow=("passenger_flow", "sum"),
            mean_record_flow=("passenger_flow", "mean"),
            max_record_flow=("passenger_flow", "max"),
            lines=("line", lambda s: s.replace("nan", pd.NA).dropna().nunique()),
            stations=("station", lambda s: s.replace("nan", pd.NA).dropna().nunique()),
        )
        .reset_index()
    )
    return by_year.sort_values("year")


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    items = search_afluencia_items()
    manifest_rows = []
    frames = []
    for item in items:
        path = download_item(item)
        status = "downloaded" if path else "download_failed"
        manifest_rows.append({**item, "local_file": path.name if path else "", "status": status})
        if path:
            frames.append(normalize_workbook(path, item.get("year")))

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(RAW_DIR / "metro_afluencia_manifest.csv", index=False)

    long_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    long_path = PROCESSED_DIR / "metro_afluencia_long.csv"
    long_df.to_csv(long_path, index=False)

    summary = summarize(long_df)
    summary_path = TABLE_DIR / "table_metro_afluencia_summary.csv"
    summary.to_csv(summary_path, index=False)

    print(f"Downloaded/checked {len(manifest)} Metro afluencia items")
    print(f"Wrote {long_path.relative_to(ROOT)} with {len(long_df):,} normalized rows")
    print(f"Wrote {summary_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
