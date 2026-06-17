"""Live data-integrity guard for the Oireachtas TD feed.

Marked ``integration`` (hits the network) and excluded from the default suite.
Run in CI with ``pytest -m integration``. This is the loud-failure backstop for
the ceased-member regression: a TD who has vacated a seat must never inflate a
constituency past its statutory seat count.
"""

import collections

import httpx
import pytest

from irl_reps.etl.oireachtas import fetch_tds

# 34th Dail (2024-): 174 seats across 43 constituencies; max district magnitude 5.
# Bump these alongside DAIL_HOUSE_NO after a boundary review / general election.
DAIL_SEATS = 174
NUM_CONSTITUENCIES = 43
MAX_SEATS_PER_CONSTITUENCY = 5


@pytest.mark.integration
def test_live_feed_matches_dail_shape():
    try:
        records = fetch_tds(httpx.Client())
    except httpx.HTTPError as exc:
        pytest.skip(f"Oireachtas API unreachable: {exc}")

    # By-election gaps may leave the chamber under-full, but never over.
    assert 0 < len(records) <= DAIL_SEATS

    per_constituency = collections.Counter(r.constituency for r in records)
    assert len(per_constituency) == NUM_CONSTITUENCIES

    over = {c: n for c, n in per_constituency.items() if n > MAX_SEATS_PER_CONSTITUENCY}
    assert not over, f"constituencies over their seat count: {over}"

    duplicates = [n for n, c in collections.Counter(r.name for r in records).items() if c > 1]
    assert not duplicates, f"duplicate TDs in feed: {duplicates}"

    # Every TD must carry a party label (Independents included).
    unlabelled = [r.name for r in records if not r.party]
    assert not unlabelled, f"TDs missing a party: {unlabelled}"
