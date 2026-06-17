"""Fetch current TDs from the official Oireachtas Open Data API.

TDs have a single authoritative source: https://api.oireachtas.ie. The API does
not publish email addresses; we derive them from the documented Oireachtas
convention (firstname.lastname@oireachtas.ie) and rely on the overrides file for
the rare exceptions.
"""

import logging
import unicodedata
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.oireachtas.ie/v1/members"
DAIL_HOUSE_NO = "34"  # 34th Dail (2024-). Bump on a general election.
_PAGE_SIZE = 100


@dataclass(frozen=True)
class TDRecord:
    name: str
    party: str | None
    constituency: str
    email: str | None


def _ascii_token(value: str | None) -> str:
    """Reduce a name part to its email token: ASCII, lowercase, alphanumerics only.

    Strips diacritics, apostrophes, hyphens and internal spaces, so "Ó Murchú"
    -> "omurchu", "Healy-Rae" -> "healyrae", "Mary Lou" -> "marylou".
    """
    if not value:
        return ""
    normalised = unicodedata.normalize("NFKD", value)
    ascii_value = normalised.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_value.lower() if ch.isalnum())


def derive_email(first_name: str | None, last_name: str | None) -> str | None:
    """Apply the Oireachtas convention: forename.surname@oireachtas.ie.

    Built from the API's structured ``firstName``/``lastName`` fields rather than
    splitting ``fullName``, which correctly handles compound forenames
    ("Mary Lou" -> marylou) and multi-token surnames ("Ó Murchú" -> omurchu).

    Still imperfect for dropped middle names (the address for "Paul Nicholas
    Gogarty" is paul.gogarty, not paulnicholas.gogarty) and nicknames ("Ged" ->
    gerald); those few exceptions live in ``data/overrides.yaml``.
    """
    forename = _ascii_token(first_name)
    surname = _ascii_token(last_name)
    if not forename or not surname:
        return None
    return f"{forename}.{surname}@oireachtas.ie"


def _is_current(date_range: dict) -> bool:
    """A membership/represent is current when its end date is unset."""
    return (date_range or {}).get("end") in (None, "")


def _membership_for_dail(member: dict, house_no: str) -> dict | None:
    """Return the member's *current* membership of the given Dail, if any.

    A member may hold several memberships of the same house (e.g. a seat that
    ended when they left, then a fresh one after a by-election). Only a
    membership whose ``dateRange.end`` is unset counts: this excludes TDs who
    have since vacated their seat (resignation, election to higher office, etc.).
    """
    for wrapper in member.get("memberships", []):
        membership = wrapper.get("membership", {})
        house = membership.get("house", {})
        if (
            house.get("houseCode") == "dail"
            and str(house.get("houseNo")) == house_no
            and _is_current(membership.get("dateRange", {}))
        ):
            return membership
    return None


def _parse_member(member: dict, house_no: str) -> TDRecord | None:
    membership = _membership_for_dail(member, house_no)
    if membership is None:
        return None
    constituency = next(
        (
            rep.get("represent", {}).get("showAs")
            for rep in membership.get("represents", [])
            if rep.get("represent", {}).get("representType") == "constituency"
            and _is_current(rep.get("represent", {}).get("dateRange", {}))
        ),
        None,
    )
    if not constituency:
        return None
    party = next(
        (
            p.get("party", {}).get("showAs")
            for p in membership.get("parties", [])
            if p.get("party", {}).get("dateRange", {}).get("end") in (None, "")
        ),
        None,
    )
    name = member.get("fullName", "").strip()
    if not name:
        return None
    email = derive_email(member.get("firstName"), member.get("lastName"))
    return TDRecord(name=name, party=party, constituency=str(constituency), email=email)


def fetch_tds(client: httpx.Client, house_no: str = DAIL_HOUSE_NO) -> list[TDRecord]:
    """Fetch all TDs of the given Dail. Raises on HTTP failure (caller handles)."""
    records: list[TDRecord] = []
    skip = 0
    while True:
        response = client.get(
            API_URL,
            params={
                "chamber": "dail",
                "house_no": house_no,
                "limit": _PAGE_SIZE,
                "skip": skip,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            break
        for item in results:
            record = _parse_member(item.get("member", {}), house_no)
            if record is not None:
                records.append(record)
        skip += _PAGE_SIZE
    logger.info("fetched TDs", extra={"ctx": {"count": len(records), "house_no": house_no}})
    return records
