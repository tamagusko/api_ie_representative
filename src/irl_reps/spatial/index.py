"""Fast point-in-polygon lookup backed by a Shapely STRtree."""

from dataclasses import dataclass

import geopandas as gpd
from shapely import Point, STRtree
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class ConstituencyMatch:
    dail_constituency: str


class _Layer:
    """One STRtree over a set of polygons with parallel name rows."""

    def __init__(self, geometries: list[BaseGeometry], names: list[str]) -> None:
        self._tree = STRtree(geometries)
        self._names = names

    def query(self, point: Point) -> str | None:
        candidates = self._tree.query(point, predicate="intersects")
        if len(candidates) == 0:
            return None
        # A point exactly on a shared boundary can intersect two polygons;
        # pick the lowest index for a deterministic answer.
        return self._names[int(min(candidates))]


class SpatialIndex:
    """Point -> Dail constituency lookups."""

    def __init__(self, constituencies: gpd.GeoDataFrame) -> None:
        names = [str(n) for n in constituencies["name"]]
        self._layer = _Layer(list(constituencies.geometry), names)
        self._constituencies = sorted(set(names))

    @property
    def constituencies(self) -> list[str]:
        """All Dail constituencies present in the boundary data, sorted."""
        return list(self._constituencies)

    def locate_constituency(self, lat: float, lon: float) -> ConstituencyMatch | None:
        name = self._layer.query(Point(lon, lat))
        if name is None:
            return None
        return ConstituencyMatch(dail_constituency=name)
