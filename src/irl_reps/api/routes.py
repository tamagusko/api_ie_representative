"""Route handlers. Thin: parse input, delegate to LookupService, return schema."""

from importlib.resources import files
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, Response

from irl_reps.config import IRELAND_BBOX
from irl_reps.schemas import (
    ConstituencyList,
    ConstituencyTDs,
    Coordinate,
    ErrorResponse,
    LookupResponse,
)
from irl_reps.service import LookupService

router = APIRouter()

_MIN_LAT, _MIN_LON, _MAX_LAT, _MAX_LON = IRELAND_BBOX

_RESPONSES: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorResponse, "description": "Coordinate not in any covered area"},
    422: {"model": ErrorResponse, "description": "Coordinate outside Ireland or malformed"},
}

_INDEX_HTML = (files("irl_reps") / "web" / "index.html").read_text(encoding="utf-8")


def _service(request: Request) -> LookupService:
    return request.app.state.lookup_service


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> str:
    return _INDEX_HTML


@router.get("/lookup", response_model=LookupResponse, responses=_RESPONSES)
async def lookup_get(
    request: Request,
    lat: Annotated[float, Query(ge=_MIN_LAT, le=_MAX_LAT)],
    lon: Annotated[float, Query(ge=_MIN_LON, le=_MAX_LON)],
) -> LookupResponse:
    return _service(request).lookup(lat, lon)


@router.post("/lookup", response_model=LookupResponse, responses=_RESPONSES)
async def lookup_post(request: Request, coordinate: Coordinate) -> LookupResponse:
    return _service(request).lookup(coordinate.lat, coordinate.lon)


@router.get("/constituencies", response_model=ConstituencyList)
async def constituencies(request: Request) -> ConstituencyList:
    return _service(request).constituencies()


@router.get(
    "/constituencies/{name}",
    response_model=ConstituencyTDs,
    responses={404: {"model": ErrorResponse, "description": "Unknown constituency name"}},
)
async def constituency(request: Request, name: str) -> ConstituencyTDs:
    return _service(request).constituency_tds(name)


@router.get("/boundaries", include_in_schema=False)
async def boundaries(request: Request) -> Response:
    return Response(
        content=request.app.state.boundaries_geojson,
        media_type="application/geo+json",
    )


@router.get("/health")
async def health(request: Request) -> dict[str, str | None]:
    return {
        "status": "ok",
        "data_last_updated": request.app.state.store.last_updated(),
    }
