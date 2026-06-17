"""`refresh-reps` CLI: the standalone monthly refresh command.

Schedule externally (cron / GitHub Actions); the API never triggers it.
"""

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

from irl_reps.config import Settings
from irl_reps.etl.build import refresh
from irl_reps.logging import configure_logging

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refresh-reps",
        description="Rebuild the representative datastore (constituency boundaries + TDs).",
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="Override the data directory")
    parser.add_argument(
        "--skip-boundaries", action="store_true", help="Do not touch boundary data"
    )
    parser.add_argument(
        "--force-boundaries",
        action="store_true",
        help="Re-download and rebuild boundary data even if present",
    )
    parser.add_argument(
        "--constituency-url", default=None, help="Override the constituency dataset URL"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _build_parser().parse_args(argv)

    settings = Settings()
    overrides: dict[str, object] = {}
    if args.data_dir is not None:
        overrides["data_dir"] = args.data_dir.resolve()
    if args.constituency_url is not None:
        overrides["constituency_url"] = args.constituency_url
    if overrides:
        settings = dataclasses.replace(settings, **overrides)  # type: ignore[arg-type]

    try:
        report = refresh(
            settings,
            skip_boundaries=args.skip_boundaries,
            force_boundaries=args.force_boundaries,
        )
    except Exception:
        logger.exception("refresh failed")
        return 1

    for source, status in sorted(report.source_status.items()):
        print(f"{source}: {status}")
    print(f"overrides applied: {report.overrides_applied}")
    print(f"last_updated: {report.last_updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
