"""Download and normalise the Dail constituency boundaries into GeoParquet.

Source (open data via data.gov.ie / Tailte Eireann, see README):
- Dail Constituencies (ungeneralised, 2023; in force for the 34th Dail).

Output columns: name, geometry (WGS84), with multipolygon parts dissolved per
constituency.
"""

import json
import logging
import re
import time
from pathlib import Path

import geopandas as gpd
import httpx

from irl_reps.config import Settings

logger = logging.getLogger(__name__)

# Candidate attribute names per source dataset vintage. Resolution is by first
# match so newer dataset releases only need a new candidate appended.
_CONSTITUENCY_NAME_CANDIDATES = ("ENG_NAME_VALUE", "CON_DESC", "ENGLISH", "CONSTITUENCY", "NAME")

_SEAT_COUNT_RE = re.compile(r"\s*\(\d+\)\s*$")

# Irish Transverse Mercator (metres). Source boundaries arrive in this CRS, so a
# metre-based simplification tolerance applies directly; geographic inputs are
# reprojected here first.
_ITM_CRS = 2157


def _simplify_gdf(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    """Douglas-Peucker simplify in projected metres, preserving topology.

    Returns the frame unchanged when ``tolerance_m`` is non-positive. The result
    may be in ITM rather than the input CRS; callers reproject to WGS84 after.
    """
    if tolerance_m <= 0:
        return gdf
    work = gdf.to_crs(_ITM_CRS) if gdf.crs is not None and gdf.crs.is_geographic else gdf.copy()
    work["geometry"] = work.geometry.simplify(tolerance_m, preserve_topology=True)
    return work


def _pick_column(gdf: gpd.GeoDataFrame, candidates: tuple[str, ...], what: str) -> str:
    for candidate in candidates:
        if candidate in gdf.columns:
            return candidate
    raise ValueError(
        f"Could not find {what} column. Tried {candidates}, dataset has {list(gdf.columns)}. "
        "Append the new column name to the candidate list in etl/boundaries.py."
    )


def _smart_title(value: str) -> str:
    """Title-case an ALL CAPS Irish name; fix lowercase joining words."""
    cleaned = value.strip()
    if not cleaned.isupper():
        return cleaned
    return cleaned.title().replace(" And ", " and ").replace(" Of ", " of ")


def process_constituency_frame(
    gdf: gpd.GeoDataFrame, *, simplify_tolerance: float = 0.0
) -> gpd.GeoDataFrame:
    """Normalise the constituency dataset; strip seat counts and dissolve parts."""
    name_col = _pick_column(gdf, _CONSTITUENCY_NAME_CANDIDATES, "constituency name")
    out = gpd.GeoDataFrame(
        {"name": gdf[name_col].map(lambda v: _smart_title(_SEAT_COUNT_RE.sub("", str(v))))},
        geometry=gdf.geometry,
        crs=gdf.crs,
    )
    dissolved = out.dissolve(by="name", as_index=False)[["name", "geometry"]]
    return _simplify_gdf(dissolved, simplify_tolerance).to_crs(4326)


_PENDING_MAX_ATTEMPTS = 20
_PENDING_WAIT_SECONDS = 15.0


def _is_pending_payload(path: Path) -> bool:
    """ArcGIS download API returns a small JSON status stub while it generates
    the export file server-side."""
    if path.stat().st_size > 4096:
        return False
    try:
        payload = json.loads(path.read_text())
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("status") in {"Pending", "InProgress"}


def _is_usable_raw(path: Path) -> bool:
    """A cached raw file is reusable unless missing or a leftover pending stub."""
    return path.exists() and not _is_pending_payload(path)


def _download(client: httpx.Client, url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("downloading boundary dataset", extra={"ctx": {"url": url, "dest": str(dest)}})
    for attempt in range(_PENDING_MAX_ATTEMPTS):
        with client.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)
        if not _is_pending_payload(dest):
            return dest
        logger.info(
            "download pending, retrying",
            extra={"ctx": {"url": url, "attempt": attempt + 1}},
        )
        time.sleep(_PENDING_WAIT_SECONDS)
    raise TimeoutError(f"Download never became ready: {url}")


def ensure_boundaries(
    settings: Settings, client: httpx.Client, *, force: bool = False
) -> Path:
    """Build ``boundaries.parquet`` if missing (or ``force``). Idempotent.

    The raw download is cached in ``data/raw`` and reused unless ``force``.
    """
    out_path = settings.boundaries_path
    if out_path.exists() and not force:
        logger.info("boundaries up to date", extra={"ctx": {"path": str(out_path)}})
        return out_path

    dest = settings.raw_dir / "constituencies.geojson"
    if force or not _is_usable_raw(dest):
        _download(client, settings.constituency_url, dest)

    constituencies = process_constituency_frame(
        gpd.read_file(dest), simplify_tolerance=settings.simplify_tolerance_m
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    constituencies.to_parquet(out_path)
    logger.info(
        "boundaries built",
        extra={"ctx": {"path": str(out_path), "constituencies": len(constituencies)}},
    )
    return out_path
