"""Application settings and constants."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Generous bounding box for the island of Ireland: (min_lat, min_lon, max_lat, max_lon).
# Coordinates outside this box are rejected with 422 before any spatial work.
IRELAND_BBOX: tuple[float, float, float, float] = (51.3, -10.7, 55.5, -5.4)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    """Data directory, overridable via ``IRL_REPS_DATA_DIR``.

    The env override matters when the package is installed (e.g. into a container's
    site-packages) rather than run from the source tree, where ``_PROJECT_ROOT``
    would otherwise point outside the deployment.
    """
    env = os.environ.get("IRL_REPS_DATA_DIR")
    return Path(env) if env else _PROJECT_ROOT / "data"

# Source dataset (open data). See README for the catalogue page this comes from.
# Constituency Boundaries Ungeneralised - National Electoral Boundaries - 2023
# (in force for the 34th Dail; Tailte Eireann via data.gov.ie).
DEFAULT_CONSTITUENCY_URL = (
    "https://data-osi.opendata.arcgis.com/api/download/v1/items/"
    "a37ad6a3a6ff47e4a5a0ff313b418448/geojson?layers=0"
)


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration.

    All paths derive from ``data_dir`` so tests can point the whole app at a
    temporary directory.
    """

    data_dir: Path = field(default_factory=_default_data_dir)
    constituency_url: str = DEFAULT_CONSTITUENCY_URL
    # Douglas-Peucker tolerance in metres, applied to boundary geometries at ETL
    # time. Shrinks the parquet and the in-memory index with no meaningful effect
    # on point-in-polygon results at constituency scale. 0 disables.
    simplify_tolerance_m: float = 25.0

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def boundaries_path(self) -> Path:
        return self.data_dir / "processed" / "boundaries.parquet"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "representatives.db"

    @property
    def overrides_path(self) -> Path:
        return self.data_dir / "overrides.yaml"
