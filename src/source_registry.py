"""Source freshness, deduplication, and local research ledger utilities."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


OFFICIAL_DOMAINS = {
    "cbr.ru",
    "minfin.gov.ru",
    "rosstat.gov.ru",
    "government.ru",
    "kremlin.ru",
    "rg.ru",
    "moex.com",
    "nspk.ru",
    "spimex.com",
    "fedresurs.ru",
    "customs.gov.ru",
    "economy.gov.ru",
    "rzd.ru",
    "dom.rf",
}

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "yclid",
    "ysclid",
    "from",
    "fbclid",
    "gclid",
}


@dataclass
class SourceDecision:
    keep: bool
    reason: str
    canonical_url: str
    domain: str
    published_at: str | None
    official: bool
    duplicate: bool = False
    old: bool = False
    undated: bool = False


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_domain(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    if "://" in text:
        text = urlparse(text).netloc.lower()
    else:
        text = text.split("/")[0].split("?")[0].split("#")[0]
    if text.startswith("www."):
        text = text[4:]
    return text


def _domain_matches(domain: str, allowed_domains: set[str]) -> bool:
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in allowed_domains)


def _allowed_domains_from_policy(policy: dict | None) -> set[str]:
    source_policy = (policy or {}).get("source_policy") or {}
    result: set[str] = set()
    for key in ("primary_domains", "secondary_domains"):
        for raw_domain in source_policy.get(key, []) or []:
            normalized = _normalize_domain(str(raw_domain))
            if normalized:
                result.add(normalized)
    return result


def ledger_path() -> Path:
    return Path(os.getenv("RESEARCH_LEDGER_FILE", "research_ledger.json"))


def load_ledger(path: Path | None = None) -> dict:
    path = path or ledger_path()
    if not path.exists():
        return {"sources": {}, "events": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("sources", {})
            data.setdefault("events", {})
            return data
    except Exception:
        pass
    return {"sources": {}, "events": {}}


def save_ledger(ledger: dict, path: Path | None = None) -> None:
    path = path or ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Не удалось сохранить research ledger: {e}")


def domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(query_pairs, doseq=True)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))


def is_official_domain(domain: str) -> bool:
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in OFFICIAL_DOMAINS)


def parse_source_date(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None

    normalized = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def max_age_for_time_range(time_range: str | None) -> timedelta:
    mapping = {
        "day": timedelta(days=2),
        "week": timedelta(days=10),
        "month": timedelta(days=35),
        "year": timedelta(days=370),
    }
    return mapping.get(time_range or "month", timedelta(days=35))


def max_age_for_policy(time_range: str | None, policy: dict | None = None) -> timedelta:
    freshness = (policy or {}).get("freshness") or {}
    window_days = freshness.get("window_days")
    try:
        if window_days:
            return timedelta(days=int(window_days) + 1)
    except Exception:
        pass
    return max_age_for_time_range(time_range)


def text_hash(*parts: object) -> str:
    text = "\n".join(str(p or "").strip().lower() for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def should_keep_source(
    *,
    url: str,
    published_date: object,
    title: str,
    content: str,
    ledger: dict,
    seen_urls: set[str],
    time_range: str | None,
    policy: dict | None = None,
    now: datetime | None = None,
) -> SourceDecision:
    canonical = canonicalize_url(url)
    domain = domain_from_url(canonical)
    official = is_official_domain(domain)
    published_dt = parse_source_date(published_date)
    published_iso = published_dt.date().isoformat() if published_dt else None
    now = now or datetime.now(timezone.utc)

    if canonical and canonical in seen_urls:
        return SourceDecision(False, "duplicate_in_run", canonical, domain, published_iso, official, duplicate=True)

    sources = ledger.setdefault("sources", {})
    existing = sources.get(canonical) if canonical else None
    source_policy = (policy or {}).get("source_policy") or {}
    allow_reuse_official = source_policy.get("allow_reuse_official", True)
    allow_undated_non_official = source_policy.get("allow_undated_non_official", False)
    min_content_chars = _env_int("SOURCE_MIN_CONTENT_CHARS", 80)

    allowed_domains = _allowed_domains_from_policy(policy)
    if allowed_domains and not _domain_matches(domain, allowed_domains):
        return SourceDecision(False, "domain_not_allowed", canonical, domain, published_iso, official)

    if existing and (not official or not allow_reuse_official):
        return SourceDecision(False, "duplicate_ledger", canonical, domain, published_iso, official, duplicate=True)

    if published_dt:
        if published_dt > now + timedelta(days=1):
            return SourceDecision(False, "future_date", canonical, domain, published_iso, official)
        if now - published_dt > max_age_for_policy(time_range, policy):
            return SourceDecision(False, "old", canonical, domain, published_iso, official, old=True)
    elif not official and not allow_undated_non_official:
        return SourceDecision(False, "undated_non_official", canonical, domain, None, official, undated=True)

    if not official:
        signal_text = f"{title or ''}\n{content or ''}".strip()
        if len(signal_text) < min_content_chars:
            return SourceDecision(False, "low_signal", canonical, domain, published_iso, official)

    snippet_hash = text_hash(title, content)
    for entry in sources.values():
        if entry.get("snippet_hash") == snippet_hash and not official:
            return SourceDecision(False, "duplicate_content", canonical, domain, published_iso, official, duplicate=True)

    return SourceDecision(True, "kept", canonical, domain, published_iso, official)


def record_source(
    ledger: dict,
    *,
    decision: SourceDecision,
    original_url: str,
    title: str,
    content: str,
    query: str,
    run_id: int | None = None,
) -> None:
    if not decision.canonical_url:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    sources = ledger.setdefault("sources", {})
    entry = sources.setdefault(
        decision.canonical_url,
        {
            "canonical_url": decision.canonical_url,
            "original_url": original_url,
            "domain": decision.domain,
            "official": decision.official,
            "first_seen": now_iso,
            "used_runs": [],
            "queries": [],
        },
    )
    entry["last_seen"] = now_iso
    entry["published_at"] = decision.published_at
    entry["title"] = title
    entry["snippet_hash"] = text_hash(title, content)
    entry["status"] = "used" if decision.keep else "rejected_" + decision.reason
    if query and query not in entry.setdefault("queries", []):
        entry["queries"].append(query)
    if run_id is not None and run_id not in entry.setdefault("used_runs", []):
        entry["used_runs"].append(run_id)
