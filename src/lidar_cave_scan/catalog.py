"""Public SAR catalog search utilities."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Sequence

ENDPOINT = "https://stac.dataspace.copernicus.eu/v1/search"


def search_sentinel1_slc(bbox: Sequence[float], start: str, end: str, limit: int = 100) -> dict:
    payload = {
        "collections": ["sentinel-1-slc"],
        "bbox": list(bbox),
        "datetime": f"{start}/{end}",
        "limit": limit,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "LiDAR-Cave-Scan/2.1",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def run_catalog_search(bbox: Sequence[float], start: str, end: str, out_path: str, limit: int = 100) -> Path:
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid WGS84 bbox.")
    result = search_sentinel1_slc(bbox, start, end, limit)
    rows = []
    for item in result.get("features", []):
        props = item.get("properties", {})
        rows.append(
            {
                "id": item.get("id"),
                "datetime": props.get("datetime"),
                "platform": props.get("platform"),
                "sar_instrument_mode": props.get("sar:instrument_mode"),
                "polarizations": props.get("sar:polarizations"),
                "assets": item.get("assets", {}),
                "microdoppler_eligible": "not_assessed",
            }
        )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "source": ENDPOINT,
                "query": {
                    "bbox": list(bbox),
                    "start": start,
                    "end": end,
                    "limit": limit,
                },
                "items": rows,
                "warning": "Catalog only. SLC availability does not establish micro-Doppler suitability.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"{len(rows)} acquisitions -> {out}")
    return out
