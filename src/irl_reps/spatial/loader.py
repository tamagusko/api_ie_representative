"""Load processed boundary data from GeoParquet."""

import logging
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = {"name", "geometry"}


def load_boundaries(path: Path) -> gpd.GeoDataFrame:
    """Load the processed Dail constituency boundaries.

    Args:
        path: Path to ``boundaries.parquet`` produced by the ETL.

    Returns:
        A GeoDataFrame of constituencies in WGS84 (columns: ``name``, ``geometry``).

    Raises:
        FileNotFoundError: When the file does not exist (run the ETL first).
        ValueError: When the file is missing required columns.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Boundary file not found: {path}. Run `refresh-reps` to build it."
        )
    gdf = gpd.read_parquet(path)
    missing = _REQUIRED_COLUMNS - set(gdf.columns)
    if missing:
        raise ValueError(f"Boundary file {path} missing columns: {sorted(missing)}")
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    gdf = gdf.reset_index(drop=True)
    logger.info("boundaries loaded", extra={"ctx": {"constituencies": len(gdf)}})
    return gdf


def constituency_outlines_geojson(constituencies: gpd.GeoDataFrame) -> str:
    """Constituency outlines as a GeoJSON FeatureCollection string.

    Each feature carries the constituency ``name`` so the map can draw and
    label them.
    """
    return constituencies[["name", "geometry"]].to_json()
