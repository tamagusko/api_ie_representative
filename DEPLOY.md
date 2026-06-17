# Deploying the API for free

The app loads the boundary index into memory at startup. After ETL geometry
simplification (`simplify_tolerance_m`, default 25 m) the index is ~1.5 MB and the
resident footprint is ~120 MB, so it fits comfortably on free tiers.

## Recommendation for collisiontracker.ie

Run it as a small public service on its own subdomain and let both
collisiontracker.ie and the public use it:

- **Name**: `api.reps.ie` is taken-sounding; use a subdomain you already own —
  `api.collisiontracker.ie` (or `reps.collisiontracker.ie`). It serves the JSON
  API and a tiny demo page at `/`.
- **Host**: **Hugging Face Spaces** (Docker, 16 GB RAM, free) for the simplest
  always-on option, or **Fly.io** if you want the subdomain managed entirely in
  your own infra. Both below.
- **Make it safe and fast for the public**: put **Cloudflare** (free) in front of
  the subdomain. You get TLS, caching, and rate-limiting without touching the
  app. The API is already read-only, has no secrets, validates all input, and
  sends open CORS for `GET` — so it is safe to expose; Cloudflare just protects
  it from abuse. Responses are cacheable (data changes monthly), so set a
  Cloudflare cache rule (e.g. 1 hour) on `/lookup*` and `/constituencies*`.

Custom domain (same steps on any host): add a `CNAME` from
`api.collisiontracker.ie` to the host's target (HF: `<user>-<space>.hf.space`;
Fly: your `*.fly.dev`), then add the domain in the host's dashboard so it issues
the certificate. With Cloudflare, the CNAME lives in Cloudflare DNS (proxied).

The image bakes the prebuilt data (`data/processed/boundaries.parquet`,
`data/representatives.db`). Refresh it on the host before building:

```bash
uv run refresh-reps          # rebuilds constituency boundaries + fetches TDs
docker build -t irl-reps .
docker run --rm -p 7860:7860 irl-reps
curl "http://127.0.0.1:7860/lookup?lat=53.3220&lon=-6.2900"
```

## Option A — Hugging Face Spaces (recommended)

16 GB RAM free, Docker-native, public URL. Best fit.

1. Create a new **Docker** Space.
2. Push this repo to it. The Space's root `README.md` must start with this
   frontmatter (Spaces reads `app_port` from it):

   ```yaml
   ---
   title: Irish TD Lookup
   emoji: 🗳️
   colorFrom: green
   colorTo: blue
   sdk: docker
   app_port: 7860
   pinned: false
   ---
   ```

3. The 1.5 MB parquet and small DB commit fine without Git LFS. If you later bake a
   larger DB, track binaries with LFS: `git lfs track "*.parquet" "*.db"`.
4. The Space builds the Dockerfile and serves at
   `https://<user>-<space>.hf.space/lookup?lat=53.3220&lon=-6.2900`.

To make the Space self-refresh at build instead of committing data, edit the
`Dockerfile`: remove the two data `COPY` lines and uncomment `RUN uv run
refresh-reps` (build then needs network and runs ~minutes).

## Option B — Render

Free web service, 512 MB RAM. Sleeps after 15 min idle (~30 s cold start) and the
disk is ephemeral, so baking data into the image (as the Dockerfile does) is
required — do not rely on a runtime `refresh-reps`.

- New → Web Service → from repo → Runtime: Docker.
- No start command needed (the Dockerfile `CMD` runs uvicorn on 7860); Render maps
  `$PORT` automatically, or set the port to 7860.

## Option C — Fly.io

3 small VMs free. 256 MB may be tight with GeoPandas loaded; use 512 MB.

```bash
fly launch --no-deploy        # detects the Dockerfile
fly deploy
```

Scale memory if the VM OOMs at boot: `fly scale memory 512`.

## The web page

Visiting the deployed root (e.g. `https://api.collisiontracker.ie/`) serves a
small map page anyone can use — click a point or pick a constituency to see
its TDs. To embed it on collisiontracker.ie instead, host the single file
`src/irl_reps/web/index.html` anywhere (or `<iframe>` the API root) and point it
at the API with a query string: `index.html?api=https://api.collisiontracker.ie`.
Because CORS is open for `GET`, the page works from any origin.

## Not recommended

Vercel / Netlify / Cloudflare Workers — serverless model reloads the index per
cold start and caps bundle size; a long-lived process (the options above) is the
right shape for this app.

## Refresh cadence

Representative data changes between elections, not daily. Re-run `uv run
refresh-reps` monthly (or after a co-option), rebuild, redeploy. `data_last_updated`
in every response and at `/health` reflects the last successful ETL.
