"""Check-time URL features used by the local PhiUSIIL research candidate."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

import tldextract


FEATURE_ORDER = [
    "url_length",
    "dot_count",
    "has_ip_address",
    "has_at_symbol",
    "hyphen_count",
    "host_length",
    "path_length",
    "path_depth",
    "query_length",
    "query_param_count",
    "tld_length",
    "subdomain_count",
    "digit_count",
    "digit_ratio",
    "letter_count",
    "letter_ratio",
    "underscore_count",
    "percent_count",
    "ampersand_count",
    "equals_count",
    "question_count",
    "has_nondefault_port",
    "has_fragment",
]

_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def extract_url_features(raw_url: str) -> list[float]:
    value = str(raw_url).strip()
    candidate = value if "://" in value else f"//{value}"
    parsed = urlsplit(candidate)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""
    suffix_data = _EXTRACTOR(host) if host else None
    suffix = suffix_data.suffix if suffix_data else ""
    registrable = suffix_data.top_domain_under_public_suffix if suffix_data else ""
    subdomain_count = (
        len([part for part in suffix_data.subdomain.split(".") if part])
        if suffix_data and registrable
        else 0
    )
    try:
        port = parsed.port
    except ValueError:
        port = None

    scheme = parsed.scheme.lower()
    nondefault_port = int(
        port is not None
        and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443))
    )
    digit_count = sum(char.isdigit() for char in value)
    letter_count = sum(char.isalpha() for char in value)
    path_depth = len([segment for segment in path.split("/") if segment])
    query_param_count = query.count("&") + 1 if query else 0

    try:
        ipaddress.ip_address(host)
        has_ip = 1
    except ValueError:
        has_ip = 0

    return [
        len(value), value.count("."), has_ip, int("@" in value), value.count("-"),
        len(host), len(path), path_depth, len(query), query_param_count,
        len(suffix), subdomain_count, digit_count, digit_count / max(1, len(value)),
        letter_count, letter_count / max(1, len(value)), value.count("_"),
        value.count("%"), query.count("&"), query.count("="), query.count("?"),
        nondefault_port, int(bool(parsed.fragment)),
    ]
