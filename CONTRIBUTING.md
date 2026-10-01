# Contributing

Thanks for helping keep the Irish TD Lookup accurate and useful. This is a
small, deliberately simple service, and contributions are easiest to accept
when they stay that way.

## Reporting wrong data

The most valuable contribution is a correction. If a TD, party or email is
wrong, open an issue with:

- the constituency and the TD concerned,
- what the API returns now and what it should return,
- a link to an official source (oireachtas.ie, the party, or the TD's own page).

Data fixes go in [`data/overrides.yaml`](data/overrides.yaml), which is applied
last on every refresh and always wins. Please don't edit
`data/representatives.db` by hand; it is rebuilt by `refresh-reps`.

## Development setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run refresh-reps                                   # build local data
uv run uvicorn --factory irl_reps.api.app:create_app --port 8080
```

## Before opening a pull request

```bash
uv run ruff check .
uv run pytest
```

Both run in CI, along with `pytest -m integration` against the live
Oireachtas API. Add or update tests for any behaviour you change.

## Guidelines

- **Keep it deterministic.** Data comes only from official sources, with no
  scraping, no LLM and no guessing.
- **Keep changes small.** One concern per pull request. Discuss larger changes
  in an issue first.
- **Follow the existing layout.** Routes stay thin, logic lives in
  `service.py`, and the ETL lives in `etl/` (see the README's Architecture
  section).
- **Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org),
  e.g. `fix(etl): handle missing party field`.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
