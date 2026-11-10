"""Canonical TF query links, independent of the dashboard's rendering callbacks."""

from collections.abc import Collection
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode


@dataclass(frozen=True)
class SearchNavigation:
    dbid: str | None
    search: str
    message: str = ""


def _query_pairs(search: str | None) -> list[tuple[str, str]]:
    return parse_qsl(
        (search or "").removeprefix("?"),
        keep_blank_values=True,
        errors="strict",
        max_num_fields=100,
    )


def parse_tf_search(
    search: str | None, known_dbids: Collection[str]
) -> SearchNavigation:
    """Resolve one exact DBID; malformed, duplicate, and unknown values are safe."""
    query = search or ""
    try:
        values = [value for key, value in _query_pairs(query) if key == "tf"]
    except (ValueError, UnicodeDecodeError):
        return SearchNavigation(
            None,
            query,
            "This search link has an invalid query. Choose a TF from the search box.",
        )
    if not values:
        return SearchNavigation(None, query)
    if len(values) != 1:
        return SearchNavigation(
            None,
            query,
            "This link contains more than one TF. Choose a TF from the search box.",
        )
    if values[0] not in known_dbids:
        return SearchNavigation(
            None,
            query,
            "This link does not identify a TF in this collection. Choose a TF from the search box.",
        )
    return SearchNavigation(values[0], query)


def format_tf_search(dbid: str | None, search: str | None = None) -> str:
    """Replace the TF parameter while preserving unrelated query parameters."""
    try:
        pairs = [(key, value) for key, value in _query_pairs(search) if key != "tf"]
    except (ValueError, UnicodeDecodeError):
        pairs = []
    if dbid:
        pairs.append(("tf", dbid))
    query = urlencode(pairs)
    return f"?{query}" if query else ""


def synchronize_tf_search(
    selected_dbid: str | None,
    search: str | None,
    known_dbids: Collection[str],
    *,
    from_url: bool,
) -> SearchNavigation:
    """Apply URL navigation or a user selection without redirecting to a representative."""
    if from_url:
        return parse_tf_search(search, known_dbids)
    dbid = (
        selected_dbid
        if isinstance(selected_dbid, str) and selected_dbid in known_dbids
        else None
    )
    return SearchNavigation(dbid, format_tf_search(dbid, search))
