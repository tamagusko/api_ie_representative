# Go live: deploy + monthly auto-update

Step-by-step to put this API on Hugging Face Spaces (free) and have the TD list
refresh itself once a month. For host alternatives and Cloudflare/custom-domain
notes, see [`DEPLOY.md`](DEPLOY.md).

Replace `<user>` with your Hugging Face username and `<space>` with your Space
name (suggested: `irish-td-lookup`).

---

## Part A — code is on GitHub ✅

Already done: https://github.com/tamagusko/api_ie_representative (`main`).
If you change code later: `git push origin main` (CI runs ruff + tests).

---

## Part B — deploy to Hugging Face Spaces

1. **Create a write token**
   huggingface.co → **Settings → Access Tokens → New token** → Type **Write** → copy it.

2. **Create the Space**
   huggingface.co/new-space → Owner = you, Space name = `<space>`,
   **SDK = Docker**, visibility Public → **Create Space**.
   Its id is `<user>/<space>`.

3. **Deploy from this repo**
   ```bash
   uv run refresh-reps          # optional: refresh TD data first
   ./deploy-hf.sh https://huggingface.co/spaces/<user>/<space>
   ```
   When git prompts: **username** = your HF username, **password** = the write token.
   (`deploy-hf.sh` pushes the code + the gitignored data files to the Space.)

4. **Wait for the build, then test**
   The Space page shows *Building* → *Running* (~2–4 min). Then:
   ```bash
   curl "https://<user>-<space>.hf.space/lookup?lat=53.322&lon=-6.29"
   ```
   (URL host = `<user>-<space>` lowercased, e.g. `tamagusko-irish-td-lookup.hf.space`.)
   Visiting the root `https://<user>-<space>.hf.space/` shows the demo map page.

---

## Part C — wire the monthly auto-update

The image re-fetches current TDs at build time; a GitHub Actions cron triggers a
monthly Space rebuild. It needs two inputs:

1. GitHub repo → **Settings → Secrets and variables → Actions**
   - **Secrets** tab → **New repository secret**: name `HF_TOKEN`, value = the write token.
   - **Variables** tab → **New repository variable**: name `HF_SPACE_ID`, value = `<user>/<space>`.

2. **Test it now** (don't wait for the 1st)
   GitHub repo → **Actions** tab → **Refresh HF Space (monthly TD update)** →
   **Run workflow**. The Space should rebuild within ~1 min; afterwards `/health`
   shows a current `data_last_updated`.

Cadence lives in [`.github/workflows/refresh-space.yml`](.github/workflows/refresh-space.yml)
(`cron: "0 6 1 * *"` = 06:00 UTC on the 1st). GitHub disables scheduled workflows
after 60 days of **zero repo activity**; the monthly manual run or any commit keeps it alive.

---

## Maintenance

- **Data refresh** is automatic (monthly) once Part C is set. To force one early:
  re-run the workflow, or locally `uv run refresh-reps && ./deploy-hf.sh <url>`.
- **After a general election / boundary review**: bump `DAIL_HOUSE_NO` in
  `src/irl_reps/etl/oireachtas.py` and the three constants in
  `tests/test_data_integrity.py`, rebuild boundaries (`uv run refresh-reps`), redeploy.
- **Every API response** and `/health` carry `data_last_updated` so you can see the
  live data's age at a glance.
