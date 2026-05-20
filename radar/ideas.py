"""Idea-card generator. Takes scored items + content plan + stories, returns idea cards."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import yaml
from openai import OpenAI

log = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://models.github.ai/inference"
_DEFAULT_MODEL = "openai/gpt-4.1"

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Defensive caps so the ideas request stays well under per-model input limits.
_MAX_ITEMS = 20
_SUMMARY_CHAR_CAP = 280


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _trim(text: str | None, cap: int = _SUMMARY_CHAR_CAP) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= cap:
        return text
    return text[: cap - 3].rstrip() + "..."


def _parse_json_array(raw: str) -> list:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array in model response. First 500 chars:\n{raw[:500]}")
    return json.loads(match.group())


def _active_tracks(content_plan: dict) -> list[dict]:
    return [t for t in content_plan.get("tracks", []) if t.get("active", True)]


def _backlog_titles(content_plan: dict) -> list[str]:
    return [
        f"[{b.get('track')}] {b.get('title','')}"
        for b in content_plan.get("backlog", [])
        if b.get("status") in (None, "idea", "drafted", "scheduled")
    ]


def generate_ideas(
    scored_items: list[dict],
    content_plan: dict,
    stories: dict,
    *,
    today: str,
    iso_week: str,
    lookback_days: int,
    model: str | None = None,
    endpoint: str | None = None,
    token: str | None = None,
    min_score: int = 5,
) -> list[dict]:
    """
    Call GitHub Models with the ideas prompts. Returns a list of idea-card dicts:
        {track, title, hook, format, partner_takeaway, story_ref, source_refs,
         image_code, reasoning}
    """
    tracks = _active_tracks(content_plan)
    if not tracks:
        raise RuntimeError("No active tracks in content-plan.yaml")

    promo_count = sum(1 for it in scored_items if it.get("promo_only"))
    if promo_count:
        log.info(f"dropping {promo_count} promo-only item(s) before idea generation")
    non_promo = [it for it in scored_items if not it.get("promo_only")]

    relevant = [it for it in non_promo if it.get("relevance_score", 0) >= min_score]
    relevant.sort(key=lambda it: it.get("relevance_score", 0), reverse=True)
    if len(relevant) > _MAX_ITEMS:
        log.info(f"capping items from {len(relevant)} to top {_MAX_ITEMS} by score")
        relevant = relevant[:_MAX_ITEMS]
    if not relevant:
        log.warning(f"No items with score >= {min_score}. Generating ideas from stories only.")

    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    if not resolved_token:
        raise RuntimeError(
            "GITHUB_TOKEN not set. Locally: gh auth token. In Actions: secrets.GITHUB_TOKEN."
        )

    model = model or _DEFAULT_MODEL
    endpoint = endpoint or _DEFAULT_ENDPOINT
    client = OpenAI(base_url=endpoint, api_key=resolved_token)

    system = _load_prompt("ideas_system.md")
    user_template = _load_prompt("ideas_user.md")

    tracks_payload = [
        {"id": t["id"], "title": t["title"], "description": t.get("description", "").strip(),
         "priority": t.get("priority", 2)}
        for t in tracks
    ]

    stories_payload = [
        {"id": s["id"], "title": s["title"], "summary": s.get("summary", "").strip(),
         "learned": s.get("learned", []), "track_tags": s.get("track_tags", []),
         "status": s.get("status", "raw")}
        for s in stories.get("stories", [])
        if s.get("status") != "posted"
    ]

    items_payload = [
        {"id": it["id"], "title": it["title"], "url": it["url"],
         "source_name": it["source_name"], "relevance_score": it["relevance_score"],
         "topic_tags": it.get("topic_tags", []),
         "partner_takeaway": _trim(it.get("partner_takeaway", "")),
         "partner_summary": _trim(it.get("partner_summary", ""))}
        for it in relevant
    ]

    user_msg = user_template.format(
        iso_week=iso_week,
        today=today,
        lookback_days=lookback_days,
        tracks_yaml=yaml.safe_dump(tracks_payload, allow_unicode=True, sort_keys=False),
        stories_yaml=yaml.safe_dump(stories_payload, allow_unicode=True, sort_keys=False),
        backlog_titles="\n".join(f"- {t}" for t in _backlog_titles(content_plan)) or "(none)",
        n_items=len(items_payload),
        items_json=json.dumps(items_payload, ensure_ascii=False, indent=2),
    )

    log.info(f"generating ideas: {len(items_payload)} scored items, "
             f"{len(tracks_payload)} tracks, {len(stories_payload)} stories")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4096,
        temperature=0.5,
    )

    raw = response.choices[0].message.content or ""
    usage = response.usage
    if usage:
        log.info(f"tokens in={usage.prompt_tokens} out={usage.completion_tokens}")

    ideas = _parse_json_array(raw)
    log.info(f"received {len(ideas)} idea cards")
    return ideas
