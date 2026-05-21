"""RSS fetching with feedparser. Bounded, defensive, no surprises."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

import feedparser
from dateutil import parser as date_parser

log = logging.getLogger(__name__)

# Stop fetching anything older than this; protects against feeds with no <pubDate>
_HARD_AGE_LIMIT_DAYS = 14


@dataclass
class Item:
    id: str
    title: str
    url: str
    source_name: str
    source_weight: float
    summary: str
    published: str  # ISO 8601 string
    audio_url: str = ""  # set when the RSS item has an audio enclosure (podcast)

    def to_dict(self) -> dict:
        return asdict(self)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_date(entry) -> datetime | None:
    for field_name in ("published", "updated", "created"):
        raw = entry.get(field_name)
        if not raw:
            continue
        try:
            dt = date_parser.parse(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def _make_id(url: str, title: str) -> str:
    seed = f"{url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(seed).hexdigest()[:12]


def fetch_feed(
    name: str,
    url: str,
    weight: float,
    *,
    per_feed_cap: int,
    lookback_days: int,
) -> list[Item]:
    """Fetch one RSS feed. Returns items within lookback window, capped."""
    if not url:
        log.warning(f"[{name}] empty URL, skipping")
        return []

    try:
        parsed = feedparser.parse(url, request_headers={"User-Agent": "signal-radar/1.0"})
    except Exception as exc:
        log.warning(f"[{name}] feedparser exception: {exc}")
        return []

    if parsed.bozo and not parsed.entries:
        log.warning(f"[{name}] bozo with no entries: {parsed.bozo_exception}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(lookback_days, 1))
    hard_cutoff = datetime.now(timezone.utc) - timedelta(days=_HARD_AGE_LIMIT_DAYS)

    items: list[Item] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        published_dt = _parse_date(entry)
        if published_dt is None:
            # No date — accept but mark as now-ish so it survives downstream filters
            published_dt = datetime.now(timezone.utc)
        elif published_dt < hard_cutoff:
            continue
        elif published_dt < cutoff:
            continue

        summary = _strip_html(entry.get("summary") or entry.get("description") or "")
        if len(summary) > 600:
            summary = summary[:597] + "..."

        audio_url = ""
        for enc in (entry.get("enclosures") or []):
            href = (enc.get("href") or enc.get("url") or "").strip()
            etype = (enc.get("type") or "").lower()
            if href and (etype.startswith("audio/") or href.lower().endswith((".mp3", ".m4a", ".aac", ".ogg", ".wav"))):
                audio_url = href
                break

        items.append(
            Item(
                id=_make_id(link, title),
                title=title,
                url=link,
                source_name=name,
                source_weight=weight,
                summary=summary,
                published=published_dt.isoformat(),
                audio_url=audio_url,
            )
        )

    items.sort(key=lambda i: i.published, reverse=True)
    return items[:per_feed_cap]


def fetch_all(sources_config: dict) -> list[Item]:
    """Fetch every source in sources.yaml. Dedup by id."""
    defaults = sources_config.get("defaults", {})
    lookback = int(defaults.get("lookback_days", 2))
    per_feed_cap = int(defaults.get("per_feed_cap", 8))
    total_cap = int(defaults.get("total_candidate_cap", 60))

    all_items: dict[str, Item] = {}
    sources = sources_config.get("sources", {})
    for category, feeds in sources.items():
        for feed in feeds:
            name = feed["name"]
            url = feed.get("url", "")
            weight = float(feed.get("weight", 1.0))
            log.info(f"fetching [{category}] {name}")
            try:
                items = fetch_feed(
                    name, url, weight,
                    per_feed_cap=per_feed_cap,
                    lookback_days=lookback,
                )
            except Exception as exc:
                log.warning(f"[{name}] fetch failed: {exc}")
                continue
            for item in items:
                all_items.setdefault(item.id, item)

    sorted_items = sorted(all_items.values(), key=lambda i: i.published, reverse=True)
    return sorted_items[:total_cap]
