---
title: Irish TD Lookup
emoji: 🗳️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Irish TD Lookup API

Give it a coordinate in Ireland; it returns the Dáil constituency containing
the point and the TDs who represent it.

**Live:** <https://tamagusko-ie-representatives.hf.space> — try
[`/lookup?lat=53.322&lon=-6.29`](https://tamagusko-ie-representatives.hf.space/lookup?lat=53.322&lon=-6.29),
or open the root URL for a clickable map.

```
GET /lookup?lat=53.3220&lon=-6.2900

{
  "input": { "lat": 53.322, "lon": -6.29 },
  "area": { "dail_constituency": "Dublin Bay South" },
  "tds": [ { "name": "...", "party": "...", "role": "TD", "email": "..." } ],
  "data_last_updated": "2026-06-17"
}
```

All data is official and deterministic: TDs from the
[Oireachtas Open Data API](https://api.oireachtas.ie), constituency geometry
from the Electoral Commission boundaries (2023 review) via
[data.gov.ie](https://data.gov.ie). No scraping, no LLM.

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /` | Interactive map page: click a point or pick a constituency. |
| `GET /lookup?lat=&lon=` | Dáil constituency + TDs for a coordinate. |
| `POST /lookup` | Same, with JSON body `{"lat": …, "lon": …}`. |
| `GET /constituencies` | All Dáil constituency names, sorted. |
| `GET /constituencies/{name}` | TDs for one constituency (case-insensitive). |
| `GET /health` | Liveness + `data_last_updated`. |
| `GET /docs` | Interactive OpenAPI docs. |

Coordinates outside Ireland return a structured `422`; coordinates in the
bounding box but not in any covered constituency (Northern Ireland, open sea)
return a structured `404`. The API is read-only and public — CORS is open for
`GET`, no key required.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run refresh-reps                                          # build the data (first run)
uv run uvicorn --factory irl_reps.api.app:create_app --port 8080
```

Interactive docs at `http://localhost:8080/docs`.

`refresh-reps` downloads the constituency boundaries, fetches current TDs from
the Oireachtas API, applies `data/overrides.yaml`, and atomically writes
`data/representatives.db`. If the boundary download URL has rotated (ArcGIS Hub
URLs do), pass the current GeoJSON link: `refresh-reps --constituency-url "<url>"`.

## Docker

```bash
./run.sh          # build, start, open http://localhost:8080
./run.sh stop
```

Or manually: `docker build -t irl-reps . && docker run --rm -p 7860:7860 irl-reps`.
The image bakes the prebuilt data and re-fetches current TDs at build time.
See [DEPLOY.md](DEPLOY.md) for hosting and the monthly auto-update.

## Architecture

```
src/irl_reps/
├── config.py        # frozen Settings dataclass (paths, bbox, dataset URL)
├── schemas.py       # Pydantic v2 request/response models
├── spatial/         # GeoParquet loading + STRtree point-in-polygon index
├── repository/      # SQLite read layer (TDs, last_updated)
├── service.py       # LookupService — all business logic
├── api/             # FastAPI app factory, thin routes, structured errors
└── etl/             # refresh-reps CLI: boundaries, Oireachtas fetch, build
```

Point-in-polygon runs against an in-memory Shapely `STRtree` built at startup
(43 constituencies, microsecond lookups). SQLite holds only tabular TD data;
boundaries live in `data/processed/boundaries.parquet` (~1.5 MB after ETL
simplification). The whole service fits in ~120 MB resident memory.

## Data maintenance

- **Refresh**: `refresh-reps` is idempotent — run monthly (a GitHub Action
  rebuilds the live Space automatically, see [DEPLOY.md](DEPLOY.md)). Fail-soft:
  if the Oireachtas API is down, TD rows carry forward from the previous
  database.
- **Overrides**: `data/overrides.yaml` is applied last on every refresh and
  always wins. Supports `update` / `add` / `remove` on the `tds` table — used
  mainly to fix emails, which are derived from the official
  `firstname.lastname@oireachtas.ie` convention (the Oireachtas API does not
  publish them).
- **After a general election**: bump `DAIL_HOUSE_NO` in `etl/oireachtas.py`,
  re-run `refresh-reps --force-boundaries` if constituencies were redrawn.

## Development

```bash
uv run pytest        # spatial lookup, API contracts, ETL, fail-soft behaviour
uv run ruff check .
```
