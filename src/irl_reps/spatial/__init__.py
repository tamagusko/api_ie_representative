"""Spatial layer: boundary loading and point-in-polygon lookup."""

from .index import ConstituencyMatch, SpatialIndex
from .loader import constituency_outlines_geojson, load_boundaries

__all__ = [
    "ConstituencyMatch",
    "SpatialIndex",
    "constituency_outlines_geojson",
    "load_boundaries",
]
