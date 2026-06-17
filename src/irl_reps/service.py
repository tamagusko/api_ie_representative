"""Lookup orchestration: spatial match + TD resolution.

All business logic lives here; route handlers only translate HTTP to/from this
service.
"""

import logging

from irl_reps.repository import RepresentativeStore
from irl_reps.schemas import (
    Area,
    ConstituencyList,
    ConstituencyTDs,
    Coordinate,
    LookupResponse,
    Representative,
)
from irl_reps.spatial import SpatialIndex

logger = logging.getLogger(__name__)

ROLE_TD = "TD"


class AreaNotCoveredError(Exception):
    """Coordinate is inside the validation bbox but not in any covered area.

    Typically Northern Ireland or open sea; the coordinate is valid but the
    Republic of Ireland constituency dataset does not cover it.
    """

    def __init__(self, lat: float, lon: float) -> None:
        super().__init__(f"No Dail constituency covers ({lat}, {lon})")
        self.lat = lat
        self.lon = lon


class UnknownConstituencyError(Exception):
    """The requested constituency name does not match any Dail constituency."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown constituency: {name}")
        self.name = name


class LookupService:
    def __init__(self, index: SpatialIndex, store: RepresentativeStore) -> None:
        self._index = index
        self._store = store

    def lookup(self, lat: float, lon: float) -> LookupResponse:
        """Resolve a coordinate to its Dail constituency and TDs.

        Raises:
            AreaNotCoveredError: When no constituency contains the point.
        """
        constituency = self._index.locate_constituency(lat, lon)
        if constituency is None:
            raise AreaNotCoveredError(lat, lon)

        tds = self._store.tds_for(constituency.dail_constituency)
        logger.info(
            "lookup",
            extra={
                "ctx": {
                    "lat": lat,
                    "lon": lon,
                    "constituency": constituency.dail_constituency,
                    "tds": len(tds),
                }
            },
        )
        return LookupResponse(
            input=Coordinate(lat=lat, lon=lon),
            area=Area(dail_constituency=constituency.dail_constituency),
            tds=[
                Representative(name=t.name, party=t.party, role=ROLE_TD, email=t.email)
                for t in tds
            ],
            data_last_updated=self._store.last_updated(),
        )

    def constituencies(self) -> ConstituencyList:
        """List every Dail constituency present in the boundary data."""
        return ConstituencyList(
            constituencies=self._index.constituencies,
            data_last_updated=self._store.last_updated(),
        )

    def constituency_tds(self, name: str) -> ConstituencyTDs:
        """Resolve a constituency name to its TDs.

        Raises:
            UnknownConstituencyError: When the name matches no constituency.
        """
        wanted = name.strip().casefold()
        match = next(
            (c for c in self._index.constituencies if c.casefold() == wanted), None
        )
        if match is None:
            raise UnknownConstituencyError(name)
        tds = self._store.tds_for(match)
        return ConstituencyTDs(
            constituency=match,
            tds=[
                Representative(name=t.name, party=t.party, role=ROLE_TD, email=t.email)
                for t in tds
            ],
            data_last_updated=self._store.last_updated(),
        )
