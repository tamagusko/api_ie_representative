# Deployment

The service is a single long-lived container: the Dockerfile bakes the prebuilt
data, re-fetches current TDs at build time, and serves on port 7860. Footprint
is ~120 MB resident, so it fits free tiers. Hugging Face Spaces is the primary
target; Render and Fly.io also work.

Serverless hosts (Vercel, Netlify, Cloudflare Workers) are not a good fit — the
in-memory boundary index would reload on every cold start.

## Hugging Face Spaces (recommended)

Free, Docker-native, 16 GB RAM, public URL. Replace `<user>`/`<space>` with your
HF username and Space name.

1. **Create a write token**: huggingface.co → Settings → Access Tokens →
   New token (type **Write**).
2. **Create the Space**: huggingface.co/new-space → SDK = **Docker**,
   visibility Public.
3. **Deploy** (requires [Git LFS](https://git-lfs.com) — the Space stores the
   boundary `.parquet` via LFS):

   ```bash
   uv run refresh-reps          # optional: refresh TD data first
   ./deploy-hf.sh https://huggingface.co/spaces/<user>/<space>
   ```

   When git prompts: username = HF username, password = the write token.
   The script pushes the code plus the gitignored data files from an isolated
   worktree, without touching your working tree.
4. **Test** once the Space shows *Running* (~2–4 min):

   ```bash
   curl "https://<user>-<space>.hf.space/lookup?lat=53.322&lon=-6.29"
   ```

   The root URL serves the demo map page.

Note: the Space's `README.md` must keep the YAML frontmatter at the top of this
repo's README — Spaces reads `sdk: docker` and `app_port: 7860` from it.

## Monthly auto-update

The image re-fetches TDs at build time, so a scheduled rebuild keeps the data
current. [`.github/workflows/refresh-space.yml`](.github/workflows/refresh-space.yml)
triggers a Space rebuild at 06:00 UTC on the 1st of each month. It needs two
inputs in the GitHub repo (Settings → Secrets and variables → Actions):

- **Secret** `HF_TOKEN` — the HF write token.
- **Variable** `HF_SPACE_ID` — `<user>/<space>`.

Test it immediately via Actions → *Refresh HF Space (monthly TD update)* →
*Run workflow*; afterwards `/health` shows a current `data_last_updated`.

GitHub disables scheduled workflows after 60 days without repo activity; any
commit or manual run keeps it alive.

## Alternatives

- **Render** (free, 512 MB): New → Web Service → Runtime: Docker. Sleeps after
  15 min idle (~30 s cold start); the disk is ephemeral, so rely on the baked
  data, not a runtime refresh.
- **Fly.io**: `fly launch --no-deploy && fly deploy`. Use 512 MB
  (`fly scale memory 512`) — 256 MB is tight with GeoPandas loaded.

## Custom domain

On any host: add a `CNAME` from your subdomain to the host's target
(HF: `<user>-<space>.hf.space`), then register the domain in the host's
dashboard so it issues a certificate. Optionally put Cloudflare (free) in front
for TLS, caching, and rate limiting — responses change monthly, so a ~1 h cache
rule on `/lookup*` and `/constituencies*` is safe.

## Embedding the map page

The demo page is a single static file (`src/irl_reps/web/index.html`). Host it
anywhere and point it at the API with `index.html?api=https://<your-api-host>`
— CORS is open for `GET`, so it works from any origin.

## Maintenance

- **Data refresh** is automatic once the monthly workflow is set. To force one:
  re-run the workflow, or locally `uv run refresh-reps && ./deploy-hf.sh <url>`.
- **After a general election or boundary review**: bump `DAIL_HOUSE_NO` in
  `src/irl_reps/etl/oireachtas.py` and the constants in
  `tests/test_data_integrity.py`, rebuild (`uv run refresh-reps`), redeploy.
- Every response and `/health` carry `data_last_updated`, so live data age is
  always visible.
