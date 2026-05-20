"""Score items via GitHub Models. Batched JSON in / JSON out."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from openai import OpenAI

log = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://models.github.ai/inference"
_DEFAULT_MODEL = "openai/gpt-4.1-mini"

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# gpt-4.1-mini caps requests at 8000 input tokens. We keep summaries short and
# batch items into small chunks so the request body stays well under that.
_SUMMARY_CHAR_CAP = 400
_BATCH_SIZE = 12


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _parse_json_array(raw: str) -> list:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array in model response. First 500 chars:\n{raw[:500]}")
    return json.loads(match.group())


def _trim(text: str | None, cap: int = _SUMMARY_CHAR_CAP) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= cap:
        return text
    return text[: cap - 3].rstrip() + "..."


def _score_batch(
    client: OpenAI,
    *,
    model: str,
    system: str,
    user_template: str,
    items: list[dict],
    today: str,
    lookback_days: int,
) -> list[dict]:
    payload = [
        {
            "id": it["id"],
            "title": it["title"],
            "url": it["url"],
            "source_name": it["source_name"],
            "source_weight": it.get("source_weight", 1.0),
            "summary": _trim(it.get("summary")),
            "published": it.get("published", ""),
        }
        for it in items
    ]

    user_msg = user_template.format(
        today=today,
        lookback_days=lookback_days,
        n_items=len(payload),
        items_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4096,
        temperature=0.2,
    )
    raw = response.choices[0].message.content or ""
    usage = response.usage
    if usage:
        log.info(f"batch tokens in={usage.prompt_tokens} out={usage.completion_tokens}")
    return _parse_json_array(raw)


def score_items(
    items: list[dict],
    *,
    content_plan: dict | None = None,
    today: str,
    lookback_days: int,
    model: str | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> list[dict]:
    """
    Send items to GitHub Models for scoring. Returns list of score dicts:
        {id, relevance_score, score_reason, topic_tags, partner_takeaway, partner_summary}

    Batches into chunks of _BATCH_SIZE so the request body stays under the
    8000-token input cap on gpt-4.1-mini. One bad batch does not fail the run.

    The system prompt has an {editorial_scope} placeholder that gets filled
    from content_plan["editorial_scope"]. If no scope is provided, a generic
    default is used.
    """
    if not items:
        return []

    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    if not resolved_token:
        raise RuntimeError(
            "GITHUB_TOKEN not set. Locally: gh auth token. In Actions: secrets.GITHUB_TOKEN."
        )

    model = model or _DEFAULT_MODEL
    endpoint = endpoint or _DEFAULT_ENDPOINT

    client = OpenAI(base_url=endpoint, api_key=resolved_token)

    editorial_scope = ""
    if content_plan:
        editorial_scope = (content_plan.get("editorial_scope") or "").strip()
    if not editorial_scope:
        editorial_scope = (
            "Generic content scope. Score items on whether they offer a clear "
            "takeaway for a thoughtful professional audience."
        )

    system_template = _load_prompt("score_system.md")
    # Use replace, not .format, so curly braces inside the scope text are safe.
    system = system_template.replace("{editorial_scope}", editorial_scope)
    user_template = _load_prompt("score_user.md")

    batches = [items[i : i + _BATCH_SIZE] for i in range(0, len(items), _BATCH_SIZE)]
    log.info(f"scoring {len(items)} items in {len(batches)} batch(es) with {model}")

    all_scores: list[dict] = []
    for i, batch in enumerate(batches, 1):
        log.info(f"batch {i}/{len(batches)}: {len(batch)} items")
        try:
            scores = _score_batch(
                client,
                model=model,
                system=system,
                user_template=user_template,
                items=batch,
                today=today,
                lookback_days=lookback_days,
            )
            all_scores.extend(scores)
        except Exception as exc:
            log.error(f"batch {i}/{len(batches)} failed: {exc}")
            continue

    log.info(f"received {len(all_scores)} score entries total")
    return all_scores


def merge_scores(items: list[dict], scores: list[dict]) -> list[dict]:
    """Join items with their scores by id. Drops items with no score."""
    score_map = {s["id"]: s for s in scores if "id" in s}
    merged = []
    for item in items:
        score = score_map.get(item["id"])
        if not score:
            continue
        merged.append({
            **item,
            "relevance_score": int(score.get("relevance_score", 0)),
            "score_reason": score.get("score_reason", ""),
            "topic_tags": score.get("topic_tags", []),
            "partner_takeaway": score.get("partner_takeaway", ""),
            "partner_summary": score.get("partner_summary", ""),
            "promo_only": bool(score.get("promo_only", False)),
        })
    return merged
