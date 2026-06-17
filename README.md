# Irish TD Lookup API

Give it a coordinate in Ireland; it returns the Dáil constituency containing the
point and the TDs who represent it.

```
GET /lookup?lat=53.3220&lon=-6.2900

{
  "input": { "lat": 53.322, "lon": -6.29 },
  "area": { "dail_constituency": "Dublin Bay South" },
  "tds": [ { "name": "...", "party": "...", "role": "TD", "email": "..." } ],
  "data_last_updated": "2026-06-17"
}
```

`POST /lookup` with `{"lat": ..., "lon": ...}` works too. Coordinates outside
the island of Ireland → structured `422`. Coordinates inside the bounding box
but not in any covered constituency (Northern Ireland, open sea) → structured
`404`.

Data is fully official and deterministic: TDs come from the
[Oireachtas Open Data API](https://api.oireachtas.ie); constituency geometry
from the Electoral Commission boundaries. No scraping, no LLM.

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /` | A small web page: click a point on a map, or pick a constituency, to see its TDs. |
| `GET /lookup?lat=&lon=` | Dáil constituency + TDs for a coordinate. |
| `POST /lookup` | Same, with a JSON body `{"lat":…, "lon":…}`. |
| `GET /constituencies` | All Dáil constituencies (sorted names). |
| `GET /constituencies/{name}` | TDs for one constituency (e.g. `/constituencies/Dublin Bay South`), case-insensitive. |
| `GET /health` | Liveness + `data_last_updated`. |
| `GET /docs` | Interactive OpenAPI docs. |

The API is read-only and public: CORS is open for `GET`, so any website (or the
built-in page) can call it from the browser. No key required.

## Architecture

```
src/irl_reps/
├── config.py        # frozen Settings dataclass (paths, bbox, dataset URL)
├── schemas.py       # Pydantic v2 request/response models
├── spatial/         # GeoParquet loading + STRtree point-in-polygon index
├── repository/      # SQLite read layer (TDs, last_updated)
├── service.py       # LookupService — all business logic
├── api/             # FastAPI app factory, thin routes, structured errors
└── etl/             # refresh-reps CLI: boundaries, Oireachtas fetch, overrides, build
```

**Storage choice — plain SQLite + GeoParquet.** At query time, point-in-polygon
runs against an in-memory Shapely `STRtree` built at startup (43 constituencies;
microsecond lookups). The database only holds tabular TD data, so
SpatiaLite/DuckDB-spatial would add a native dependency for capability that is
never used. Boundaries live in `data/processed/boundaries.parquet`; TDs in
`data/representatives.db` — both rebuilt by the ETL, the DB swapped atomically.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Build the data (first run)

```bash
uv run refresh-reps
```

This downloads the constituency GeoJSON into `data/raw/`, normalises it to
`data/processed/boundaries.parquet`, fetches TDs from the Oireachtas API,
applies `data/overrides.yaml`, and atomically writes `data/representatives.db`
with a `last_updated` stamp.

Boundary geometries are simplified at ETL time (`Settings.simplify_tolerance_m`,
default 25 m), which shrinks the index with no change to point-in-polygon
results at this scale. Set it to `0` to keep full-resolution geometries.

If the dataset download URL has rotated (ArcGIS Hub URLs do), grab the current
GeoJSON link from the catalogue page below and pass it explicitly:

```bash
uv run refresh-reps --constituency-url "<geojson url>"
```

## Run the API

```bash
uv run uvicorn --factory irl_reps.api.app:create_app --port 8080
```

Interactive docs at `http://localhost:8080/docs`.

## Deployment

A `Dockerfile` bakes the prebuilt data and runs the app on port 7860. After ETL
geometry simplification the boundary index is ~1.5 MB and the container holds at
~120 MB resident, so it fits free tiers (Hugging Face Spaces, Render, Fly.io).
See [DEPLOY.md](DEPLOY.md) for step-by-step instructions.

Run it locally in Docker with one command (builds, starts, opens the browser):

```bash
./run.sh          # then open http://localhost:8080
./run.sh stop     # stop and remove the container
```

Or by hand:

```bash
docker build -t irl-reps .
docker run --rm -p 7860:7860 irl-reps
curl "http://127.0.0.1:7860/lookup?lat=53.3220&lon=-6.2900"
```

The container reads its data directory from `IRL_REPS_DATA_DIR` (set to `/app/data`
in the image).

## Monthly refresh

`refresh-reps` is standalone and idempotent — schedule it externally, e.g.
cron:

```cron
0 4 1 * * cd /path/to/api_ie_representative && uv run refresh-reps >> refresh.log 2>&1
```

or a GitHub Action on `schedule: cron: "0 4 1 * *"` that runs
`uv run refresh-reps` and commits/uploads the rebuilt `data/` artifacts.

Fail-soft behaviour: if the Oireachtas API is down, TD rows are carried forward
from the previous database and the refresh continues. Per-source outcomes are
printed and stored in `meta.source_status`.

After a general election, bump `DAIL_HOUSE_NO` in `etl/oireachtas.py` to the new
Dáil number, and re-run `refresh-reps --force-boundaries` if the constituencies
were redrawn.

## Data sources

| Data | Source |
|---|---|
| Dáil constituencies | The Electoral Commission constituency boundaries (2023 review) via [data.gov.ie](https://data.gov.ie) (search "Constituency Boundaries") |
| TDs | [Oireachtas Open Data API](https://api.oireachtas.ie) (official) |

TD emails are not published by the Oireachtas API; they are derived from the
official `firstname.lastname@oireachtas.ie` convention. Correct exceptions via
the overrides file.

## Manual overrides

`data/overrides.yaml` is applied **last** on every refresh, so it always wins
over fetched data. Supported operations on the `tds` table:

```yaml
tds:
  update:
    - match: {name: "John Example", constituency: "Dublin South-Central"}
      set: {email: "john.example@oireachtas.ie"}
  add:
    - name: "New TD"
      party: "Independent"
      email: "new.td@oireachtas.ie"
      constituency: "Dublin South-Central"
  remove:
    - {name: "Former TD"}
```

Commit the file; re-run `refresh-reps` (or wait for the scheduled run).

## Tests & lint

```bash
uv run pytest
uv run ruff check .
```

Tests cover spatial lookup (Dublin, rural, coastal-edge, Northern Ireland, open
sea), schema validation, API status codes, constituency boundary normalisation,
the Oireachtas client, override application, idempotency, and fail-soft
carry-forward.
