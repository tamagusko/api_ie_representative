"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from irl_reps.config import Settings
from irl_reps.logging import configure_logging
from irl_reps.repository import RepresentativeStore
from irl_reps.service import LookupService
from irl_reps.spatial import SpatialIndex, constituency_outlines_geojson, load_boundaries

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        constituencies = load_boundaries(app_settings.boundaries_path)
        store = RepresentativeStore(app_settings.db_path)
        app.state.store = store
        app.state.lookup_service = LookupService(SpatialIndex(constituencies), store)
        app.state.boundaries_geojson = constituency_outlines_geojson(constituencies)
        logger.info("startup complete", extra={"ctx": {"data_dir": str(app_settings.data_dir)}})
        yield
        store.close()

    app = FastAPI(
        title="Irish TD Lookup",
        description=(
            "Resolve a coordinate in Ireland to its Dail constituency and the TDs "
            "who represent it."
        ),
        version="0.2.0",
        lifespan=lifespan,
    )

    from irl_reps.api.errors import register_error_handlers
    from irl_reps.api.routes import router

    # Public, read-only API: allow any origin to call it from the browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(router)
    return app
