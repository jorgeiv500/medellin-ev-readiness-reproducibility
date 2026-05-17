#!/usr/bin/env python3
"""Create a Zenodo draft or published record for this reproducibility package.

Usage:
  ZENODO_ACCESS_TOKEN=... python scripts/zenodo/create_deposit.py
  ZENODO_ACCESS_TOKEN=... python scripts/zenodo/create_deposit.py --publish --yes-publish

The script never writes the token to disk. Publishing is irreversible, so the
publish action requires both flags.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist" / "zenodo"
VERSION = "1.0.2"
BASE_URL = "https://zenodo.org/api"
SANDBOX_BASE_URL = "https://sandbox.zenodo.org/api"


EXCLUDE_PARTS = {
    ".git",
    "dist",
}


def api_request(
    method: str,
    url: str,
    token: str,
    *,
    payload: dict[str, Any] | None = None,
    data: bytes | None = None,
    content_type: str | None = None,
) -> dict[str, Any] | list[Any] | None:
    body: bytes | None = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = data
        if content_type:
            headers["Content-Type"] = content_type

    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=300) as response:
            response_body = response.read()
            if not response_body:
                return None
            return json.loads(response_body.decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Zenodo API {method} {url} failed with HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Zenodo API {method} {url} failed: {exc}") from exc


def get_token(use_stdin: bool) -> str:
    token = os.environ.get("ZENODO_ACCESS_TOKEN") or os.environ.get("ZENODO_TOKEN")
    if token:
        return token.strip()
    if use_stdin:
        token = sys.stdin.readline().strip()
        if token:
            return token
    raise SystemExit("No Zenodo token found. Set ZENODO_ACCESS_TOKEN or pass --token-stdin.")


def current_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def iter_package_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & EXCLUDE_PARTS:
            continue
        files.append(path)
    return sorted(files)


def build_zip() -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    output = DIST / f"medellin_ev_readiness_reproducibility_v{VERSION}.zip"
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in iter_package_files():
            archive.write(path, path.relative_to(ROOT).as_posix())
    return output


def build_metadata() -> dict[str, Any]:
    commit = current_commit()
    description = """
<p>Standalone reproducibility package for a public-data analysis of public EV charging readiness in Medellin and the Valle de Aburra, Colombia.</p>
<p>The package contains code, configuration files, public-data extracts where redistribution is permitted, processed geospatial layers, publication figures, publication tables, source documentation, citation metadata, Zenodo metadata, license information, and checksums.</p>
<p>The analysis treats public EV charging as an urban planning and infrastructure-governance problem shaped by topography, mobility demand, public transport, household charging constraints, infrastructure evidence, vulnerability, and metropolitan governance.</p>
""".strip()
    return {
        "title": "Medellin Electric-Mobility Transition Readiness: Reproducibility Package",
        "upload_type": "dataset",
        "description": description,
        "creators": [
            {
                "name": "Romero-Gelvez, Jorge Ivan",
                "orcid": "0000-0002-5335-0819",
                "affiliation": "Universidad de Bogota Jorge Tadeo Lozano",
            },
            {
                "name": "Zapata, Sebastian",
                "orcid": "0000-0002-4836-8328",
                "affiliation": "Universidad EIA",
            },
        ],
        "access_right": "open",
        "license": "MIT",
        "publication_date": date.today().isoformat(),
        "version": VERSION,
        "keywords": [
            "electric vehicle charging",
            "urban planning",
            "spatial justice",
            "Medellin",
            "Valle de Aburra",
            "transport accessibility",
        ],
        "prereserve_doi": True,
        "related_identifiers": [
            {
                "identifier": "https://github.com/jorgeiv500/medellin-ev-readiness-reproducibility",
                "relation": "isSupplementedBy",
                "scheme": "url",
            },
            {
                "identifier": f"https://github.com/jorgeiv500/medellin-ev-readiness-reproducibility/tree/{commit}",
                "relation": "isSupplementedBy",
                "scheme": "url",
            },
            {
                "identifier": "https://github.com/jorgeiv500/medellin-ev-readiness-reproducibility/releases/tag/v1.0.2",
                "relation": "isVersionOf",
                "scheme": "url",
            },
        ],
        "notes": "Third-party data retain their original source licenses and reuse conditions.",
    }


def safe_result(deposition: dict[str, Any], uploaded_files: list[dict[str, Any]], published: bool) -> dict[str, Any]:
    metadata = deposition.get("metadata") or {}
    prereserve = metadata.get("prereserve_doi") or {}
    doi = metadata.get("doi") or deposition.get("doi") or prereserve.get("doi")
    links = deposition.get("links") or {}
    return {
        "published": published,
        "id": deposition.get("id"),
        "conceptrecid": deposition.get("conceptrecid"),
        "doi": doi,
        "conceptdoi": deposition.get("conceptdoi"),
        "record_url": f"https://doi.org/{doi}" if doi else None,
        "html": links.get("html"),
        "latest_draft_html": links.get("latest_draft_html"),
        "submitted": deposition.get("submitted"),
        "state": deposition.get("state"),
        "files": [
            {
                "filename": item.get("key") or item.get("filename") or item.get("name"),
                "size": item.get("size") or item.get("filesize"),
                "checksum": item.get("checksum"),
            }
            for item in uploaded_files
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", action="store_true", help="Use sandbox.zenodo.org instead of production Zenodo.")
    parser.add_argument("--token-stdin", action="store_true", help="Read the token from the first line of stdin.")
    parser.add_argument("--publish", action="store_true", help="Publish after upload.")
    parser.add_argument("--yes-publish", action="store_true", help="Confirm irreversible Zenodo publication.")
    args = parser.parse_args()

    if args.publish and not args.yes_publish:
        raise SystemExit("Publishing is irreversible. Re-run with --publish --yes-publish.")

    token = get_token(args.token_stdin)
    base = SANDBOX_BASE_URL if args.sandbox else BASE_URL
    archive = build_zip()

    print("Creating Zenodo deposition draft...")
    deposition = api_request("POST", f"{base}/deposit/depositions", token, payload={})
    assert isinstance(deposition, dict)
    deposition_id = deposition["id"]

    print(f"Updating metadata for deposition {deposition_id}...")
    deposition = api_request("PUT", f"{base}/deposit/depositions/{deposition_id}", token, payload={"metadata": build_metadata()})
    assert isinstance(deposition, dict)

    bucket = (deposition.get("links") or {}).get("bucket")
    if not bucket:
        raise RuntimeError("Zenodo response did not include an upload bucket URL.")

    print(f"Uploading {archive.name} ({archive.stat().st_size} bytes)...")
    uploaded = api_request(
        "PUT",
        f"{bucket}/{quote(archive.name)}",
        token,
        data=archive.read_bytes(),
        content_type="application/zip",
    )
    assert isinstance(uploaded, dict)
    uploaded_files = [uploaded]

    published = False
    if args.publish:
        print("Publishing Zenodo deposition...")
        deposition = api_request("POST", f"{base}/deposit/depositions/{deposition_id}/actions/publish", token)
        assert isinstance(deposition, dict)
        published = True
    else:
        deposition = api_request("GET", f"{base}/deposit/depositions/{deposition_id}", token)
        assert isinstance(deposition, dict)

    result = safe_result(deposition, uploaded_files, published)
    result_path = DIST / "zenodo_deposition_result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
