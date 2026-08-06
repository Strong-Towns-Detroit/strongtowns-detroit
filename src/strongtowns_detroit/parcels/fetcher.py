"""Fetch Detroit parcel data from the city's ArcGIS Open Data portal."""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Detroit "Parcels (Current)" dataset
_ARCGIS_ITEM_ID = "3c784c118e5c4083b37038e9b38573df"
_HUB_DOWNLOAD = (
    f"https://data.detroitmi.gov/api/download/v1/items/{_ARCGIS_ITEM_ID}"
)
_FEATURE_SERVER = (
    "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services"
    "/parcel_file_current/FeatureServer/0"
)
_PAGE_SIZE = 1000  # ArcGIS max with geometry; 2000 without
_REQUEST_TIMEOUT = 120  # seconds – the full GeoJSON is ~1.2 GB
_POLL_INTERVAL = 15  # seconds between status checks while export generates
_MAX_POLL_ATTEMPTS = 40  # ~10 minutes of polling


def _hub_download(
    url: str,
    output_path: Path,
    *,
    timeout: int = _REQUEST_TIMEOUT,
    poll_interval: int = _POLL_INTERVAL,
    max_poll_attempts: int = _MAX_POLL_ATTEMPTS,
) -> Path:
    """Download a file from the ArcGIS Hub bulk-download API with polling.

    The Hub API generates exports asynchronously.  The first request may
    return a small JSON body with ``{"status": "Pending"}``.  This helper
    polls until the export is ready, then streams the real file to disk.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, max_poll_attempts + 1):
        logger.info("Requesting %s (attempt %d) …", url, attempt)
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        content_length = int(resp.headers.get("content-length", 0))

        # A pending response is small JSON.  Real exports are large and/or
        # have a non-JSON content type (application/geo+json, text/csv, …).
        if content_length > 0 and content_length < 1024 and "json" in content_type:
            body = resp.content
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                data = {}
            if data.get("status") in ("Pending", "ExportingData"):
                pct = data.get("progressInPercent", "?")
                logger.info(
                    "  Export is being generated (%s%%) — retrying in %ds …",
                    pct,
                    poll_interval,
                )
                time.sleep(poll_interval)
                continue

        # Stream the real file to disk.
        logger.info("Downloading …")
        total = content_length
        downloaded = 0
        with open(output_path, "wb") as f:
            # If we already consumed the body above (small non-pending JSON),
            # write it directly.  Otherwise stream the response.
            if resp._content_consumed:
                f.write(resp.content)
                downloaded = len(resp.content)
            else:
                for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        logger.info("  %.1f%% (%d / %d bytes)", pct, downloaded, total)

        logger.info("Saved %d bytes to %s", downloaded, output_path)
        return output_path

    raise TimeoutError(
        f"Export not ready after {max_poll_attempts * poll_interval}s of polling: {url}"
    )


def fetch_geojson(output_path: Path, *, timeout: int = _REQUEST_TIMEOUT) -> Path:
    """Download the full Parcels GeoJSON via the ArcGIS Hub bulk-download API.

    This is a single large request (~1.2 GB) that returns the dataset
    pre-reprojected to WGS84 (CRS84), matching the existing Parcels.geojson.
    The Hub may need time to generate the export; this function polls
    automatically until the file is ready.
    """
    url = f"{_HUB_DOWNLOAD}/geojson?layers=0"
    return _hub_download(url, output_path, timeout=timeout)


def fetch_csv(output_path: Path, *, timeout: int = _REQUEST_TIMEOUT) -> Path:
    """Download parcel attribute data (no geometry) as CSV via the Hub API.

    Polls automatically if the export is still being generated.
    """
    url = f"{_HUB_DOWNLOAD}/csv?layers=0"
    return _hub_download(url, output_path, timeout=timeout)


def query_parcels(
    *,
    where: str = "1=1",
    out_fields: str = "*",
    return_geometry: bool = True,
    max_records: Optional[int] = None,
    timeout: int = 60,
) -> list[dict]:
    """Query the FeatureServer with pagination and return GeoJSON features.

    Use this for filtered or partial downloads instead of the bulk APIs.

    Parameters
    ----------
    where : str
        SQL WHERE clause, e.g. ``"zoning_district='R1'"``
    out_fields : str
        Comma-separated field names, or ``"*"`` for all.
    return_geometry : bool
        Whether to include polygon geometry in results.
    max_records : int | None
        Stop after this many records.  ``None`` fetches everything.
    timeout : int
        Per-request timeout in seconds.
    """
    features: list[dict] = []
    offset = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": _PAGE_SIZE,
        }

        logger.info("Querying FeatureServer (offset=%d) …", offset)
        resp = requests.get(f"{_FEATURE_SERVER}/query", params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        page_features = data.get("features", [])
        if not page_features:
            break

        features.extend(page_features)
        logger.info("  Fetched %d features (total: %d)", len(page_features), len(features))

        if max_records and len(features) >= max_records:
            features = features[:max_records]
            break

        exceeded = data.get("properties", {}).get("exceededTransferLimit") or data.get(
            "exceededTransferLimit"
        )
        if not exceeded and len(page_features) < _PAGE_SIZE:
            break

        offset += len(page_features)
        time.sleep(0.25)

    return features


def query_to_geojson(output_path: Path, **query_kwargs) -> Path:
    """Run :func:`query_parcels` and write results as a GeoJSON file."""
    features = query_parcels(**query_kwargs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    geojson = {
        "type": "FeatureCollection",
        "name": "Parcels",
        "features": features,
    }
    with open(output_path, "w") as f:
        json.dump(geojson, f)

    logger.info("Wrote %d features to %s", len(features), output_path)
    return output_path
