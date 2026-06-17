"""Structured JSON error handling. No stack traces ever leave the process."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from irl_reps.service import AreaNotCoveredError, UnknownConstituencyError

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = "tiago.tamagusko@ucd.ie"


def _error_body(code: str, message: str, detail: object | None = None) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}
    if detail is not None:
        error["detail"] = detail
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                code="invalid_coordinates",
                message=(
                    "Invalid input. lat/lon must be numbers within the island of Ireland "
                    "(lat 51.3 to 55.5, lon -10.7 to -5.4)."
                ),
                detail=[
                    {"field": ".".join(str(p) for p in e["loc"]), "issue": e["msg"]}
                    for e in exc.errors()
                ],
            ),
        )

    @app.exception_handler(AreaNotCoveredError)
    async def not_covered_handler(request: Request, exc: AreaNotCoveredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_body(
                code="area_not_covered",
                message=(
                    f"Coordinate ({exc.lat}, {exc.lon}) is not inside any covered "
                    "administrative area (it may be in Northern Ireland or at sea)."
                ),
            ),
        )

    @app.exception_handler(UnknownConstituencyError)
    async def unknown_constituency_handler(
        request: Request, exc: UnknownConstituencyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_body(
                code="unknown_constituency",
                message=(
                    f"'{exc.name}' is not a known Dail constituency. "
                    "See GET /constituencies for the list of valid names."
                ),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"ctx": {"path": request.url.path}})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                code="internal_error",
                message=f"Internal server error. If this persists, contact {SUPPORT_EMAIL}.",
            ),
        )
