"""Pydantic request/response schemas."""

from pydantic import BaseModel, Field

from irl_reps.config import IRELAND_BBOX

_MIN_LAT, _MIN_LON, _MAX_LAT, _MAX_LON = IRELAND_BBOX

_LAT_FIELD = Field(
    ge=_MIN_LAT,
    le=_MAX_LAT,
    description=f"Latitude within the island of Ireland ({_MIN_LAT} to {_MAX_LAT})",
)
_LON_FIELD = Field(
    ge=_MIN_LON,
    le=_MAX_LON,
    description=f"Longitude within the island of Ireland ({_MIN_LON} to {_MAX_LON})",
)


class Coordinate(BaseModel):
    """A WGS84 coordinate, constrained to the island of Ireland bounding box."""

    lat: float = _LAT_FIELD
    lon: float = _LON_FIELD


class Area(BaseModel):
    dail_constituency: str


class Representative(BaseModel):
    name: str
    party: str | None = None
    role: str
    email: str | None = None


class LookupResponse(BaseModel):
    input: Coordinate
    area: Area
    tds: list[Representative]
    data_last_updated: str | None = None


class ConstituencyList(BaseModel):
    constituencies: list[str]
    data_last_updated: str | None = None


class ConstituencyTDs(BaseModel):
    constituency: str
    tds: list[Representative]
    data_last_updated: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
