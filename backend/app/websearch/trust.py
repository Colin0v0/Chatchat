from __future__ import annotations

from datetime import datetime, timezone
import math
import re

SOCIAL_DOMAINS = (
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "youtube.com",
)
REFERENCE_DOMAINS = (
    "wikipedia.org",
    "britannica.com",
)
OFFICIAL_DOMAIN_HINTS = (".gov", ".edu", "official")
DATA_DOMAIN_HINTS = ("weather", "finance", "market", "score", "stat", "api")

DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def trust_label(domain: str, preferred_domains: tuple[str, ...], disfavored_domains: tuple[str, ...]) -> str:
    normalized = domain.lower()
    if _matches_domain(normalized, preferred_domains):
        return "preferred"
    if _matches_domain(normalized, disfavored_domains) or _matches_domain(normalized, SOCIAL_DOMAINS):
        return "low"
    if _matches_domain(normalized, REFERENCE_DOMAINS):
        return "reference"
    if any(normalized.endswith(hint) or hint in normalized for hint in OFFICIAL_DOMAIN_HINTS):
        return "official"
    if any(hint in normalized for hint in DATA_DOMAIN_HINTS):
        return "data"
    return "standard"


def trust_score(domain: str, preferred_domains: tuple[str, ...], disfavored_domains: tuple[str, ...]) -> float:
    label = trust_label(domain, preferred_domains, disfavored_domains)
    return {
        "preferred": 0.95,
        "official": 0.88,
        "reference": 0.82,
        "data": 0.78,
        "standard": 0.62,
        "low": 0.18,
    }[label]


def freshness_label(published_at: str, require_freshness: bool) -> str:
    if not published_at.strip():
        return "missing" if require_freshness else "unknown"
    age_days = _age_in_days(published_at)
    if age_days is None:
        return "unknown"
    if age_days <= 2:
        return "fresh"
    if age_days <= 14:
        return "recent"
    return "stale"


def freshness_score(published_at: str, require_freshness: bool) -> float:
    if not require_freshness:
        return 0.5
    age_days = _age_in_days(published_at)
    if age_days is None:
        return 0.2
    return max(0.0, min(1.0, math.exp(-age_days / 7.0)))


def _age_in_days(published_at: str) -> float | None:
    value = published_at.strip()
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        match = DATE_PATTERN.search(value)
        if not match:
            return None
        parsed = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 86400.0)


def _matches_domain(domain: str, candidates: tuple[str, ...]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in candidates)
