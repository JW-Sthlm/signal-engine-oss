"""
signal-engine: a content opportunity engine.

Stage 1 (this CLI): fetch RSS, score for content potential against your editorial
tracks, write a daily raw archive. On demand, generate weekly idea cards.
Stage 2 (Copilot CLI skill): polish a chosen idea card into a post in your voice.

Usage:
  python -m radar run                   # daily: fetch + score, write digests/raw/YYYY-MM-DD.md
  python -m radar run --dry-run         # print to stdout, do not save
  python -m radar run --top 8           # override top_n
  python -m radar run --no-fetch        # reuse last raw fetch (for prompt iteration)
  python -m radar ideas                 # weekly: idea cards to digests/YYYY-WW.md
  python -m radar ideas --dry-run       # print to stdout
  python -m radar ideas --lookback 7    # override window
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

from radar.fetch import fetch_all
from radar.score import score_items, merge_scores
from radar.digest import build_digest, build_ideas_digest
from radar.ideas import generate_ideas
from radar.transcribe import enrich_with_transcripts, _resolve_mode

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = REPO_ROOT / "sources.yaml"
CONTENT_PLAN_FILE = REPO_ROOT / "content-plan.yaml"
STORIES_FILE = REPO_ROOT / "stories.yaml"
DIGESTS_DIR = REPO_ROOT / "digests"
RAW_DIGESTS_DIR = DIGESTS_DIR / "raw"
WORKDIR = REPO_ROOT / "_workdir"


def _raw_only_items(items: list[dict]) -> list[dict]:
    """When scoring fails: synthesize neutral score=0 entries so digest still renders."""
    out = []
    for it in items:
        out.append({
            **it,
            "relevance_score": 0,
            "score_reason": "Scoring failed, raw fetch only.",
            "topic_tags": [],
            "partner_takeaway": "",
            "partner_summary": (it.get("summary") or "")[:300] or "(no summary)",
        })
    return out


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_sources() -> dict:
    return _load_yaml(SOURCES_FILE)


def _load_content_plan() -> dict:
    return _load_yaml(CONTENT_PLAN_FILE)


def _iso_week(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def cmd_run(args: argparse.Namespace) -> int:
    log = logging.getLogger("signal")

    cfg = _load_sources()
    content_plan = _load_content_plan()
    defaults = cfg.get("defaults", {})
    threshold = int(args.threshold or defaults.get("score_threshold", 7))
    top_n = int(args.top or defaults.get("top_n", 5))
    lookback = int(defaults.get("lookback_days", 2))

    today = date.today().isoformat()
    WORKDIR.mkdir(exist_ok=True)
    raw_cache = WORKDIR / "last_fetch.json"

    if args.no_fetch and raw_cache.exists():
        log.info(f"reusing cached fetch from {raw_cache}")
        items = json.loads(raw_cache.read_text(encoding="utf-8"))
    else:
        log.info("fetching feeds")
        items = [it.to_dict() for it in fetch_all(cfg)]
        raw_cache.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"cached {len(items)} items to {raw_cache}")

    transcribe_mode = _resolve_mode(args.transcribe)
    if transcribe_mode != "none":
        log.info(f"podcast transcription enabled (mode={transcribe_mode})")
        items = enrich_with_transcripts(items, WORKDIR, mode=transcribe_mode)

    final: list[dict] = []
    all_scored: list[dict] = []

    if not items:
        log.warning("no items fetched, writing empty digest")
    else:
        log.info(f"scoring {len(items)} items (model={args.model})")
        try:
            scores = score_items(
                items,
                content_plan=content_plan,
                today=today,
                lookback_days=lookback,
                model=args.model,
            )
            merged = merge_scores(items, scores)
            all_scored = merged
            above = [m for m in merged if m["relevance_score"] >= threshold]
            above.sort(key=lambda m: m["relevance_score"], reverse=True)
            final = above[:top_n]
            log.info(
                f"items: fetched={len(items)} scored={len(merged)} "
                f"above_threshold={len(above)} final={len(final)}"
            )
        except Exception as exc:
            log.error(f"scoring failed: {exc}")
            final = _raw_only_items(items)[:top_n]

    if all_scored:
        scored_dir = WORKDIR / "scored"
        scored_dir.mkdir(exist_ok=True)
        scored_path = scored_dir / f"{today}.json"
        scored_path.write_text(
            json.dumps(all_scored, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info(f"cached scored items to {scored_path}")

    digest_md = build_digest(final, today, threshold=threshold, top_n=top_n)

    if args.dry_run:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
        sys.stdout.write(digest_md)
        return 0

    RAW_DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RAW_DIGESTS_DIR / f"{today}.md"
    out_file.write_text(digest_md, encoding="utf-8")
    log.info(f"wrote {out_file} ({len(digest_md)} chars)")
    print(str(out_file))
    return 0


def cmd_ideas(args: argparse.Namespace) -> int:
    log = logging.getLogger("signal")

    cfg = _load_sources()
    defaults = cfg.get("defaults", {})
    lookback = int(args.lookback or 7)
    min_score = int(args.min_score or defaults.get("score_threshold", 6))

    content_plan = _load_yaml(CONTENT_PLAN_FILE)
    stories = _load_yaml(STORIES_FILE)

    today_date = date.today()
    today = today_date.isoformat()
    iso_week = _iso_week(today_date)

    cfg_for_run = dict(cfg)
    cfg_for_run["defaults"] = {**defaults, "lookback_days": lookback}

    log.info(f"fetching feeds (lookback={lookback} days)")
    items = [it.to_dict() for it in fetch_all(cfg_for_run)]
    log.info(f"fetched {len(items)} items")

    scored: list[dict] = []
    if items:
        log.info(f"scoring {len(items)} items (model={args.score_model})")
        try:
            scores = score_items(
                items,
                content_plan=content_plan,
                today=today,
                lookback_days=lookback,
                model=args.score_model,
            )
            scored = merge_scores(items, scores)
            log.info(f"scored {len(scored)} items")
        except Exception as exc:
            log.error(f"scoring failed: {exc}")
            scored = []

    log.info("generating idea cards")
    try:
        ideas = generate_ideas(
            scored,
            content_plan,
            stories,
            today=today,
            iso_week=iso_week,
            lookback_days=lookback,
            model=args.model,
            min_score=min_score,
        )
    except Exception as exc:
        log.error(f"idea generation failed: {exc}")
        return 2

    if scored:
        scored_dir = WORKDIR / "scored"
        scored_dir.mkdir(exist_ok=True)
        (scored_dir / f"{today}-ideas.json").write_text(
            json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if ideas:
        ideas_dir = WORKDIR / "ideas"
        ideas_dir.mkdir(exist_ok=True)
        (ideas_dir / f"{iso_week}.json").write_text(
            json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    source_items_by_id = {s["id"]: s for s in scored}
    stories_by_id = {s["id"]: s for s in (stories.get("stories") or [])}

    digest_md = build_ideas_digest(
        ideas,
        iso_week=iso_week,
        today=today,
        source_items_by_id=source_items_by_id,
        stories_by_id=stories_by_id,
    )

    if args.dry_run:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
        sys.stdout.write(digest_md)
        return 0

    DIGESTS_DIR.mkdir(exist_ok=True)
    out_file = DIGESTS_DIR / f"{iso_week}.md"
    out_file.write_text(digest_md, encoding="utf-8")
    log.info(f"wrote {out_file} ({len(digest_md)} chars)")
    print(str(out_file))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signal")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="daily fetch + score, write raw archive")
    run.add_argument("--dry-run", action="store_true", help="print to stdout, skip save")
    run.add_argument("--top", type=int, default=None, help="override top_n")
    run.add_argument("--threshold", type=int, default=None, help="override score_threshold")
    run.add_argument("--no-fetch", action="store_true", help="reuse last cached fetch")
    run.add_argument("--model", default="openai/gpt-4.1-mini",
                     help="GitHub Models model id (default: openai/gpt-4.1-mini)")
    run.add_argument("--transcribe", action="store_true",
                     help="enrich podcast items with transcript (requires podcast-transcriber)")
    run.set_defaults(func=cmd_run)

    ideas = sub.add_parser("ideas", help="weekly idea-card generation")
    ideas.add_argument("--dry-run", action="store_true", help="print to stdout, skip save")
    ideas.add_argument("--lookback", type=int, default=None, help="days of feed history (default 7)")
    ideas.add_argument("--min-score", type=int, default=None,
                       help="minimum score to include an item as source fuel (default 6)")
    ideas.add_argument("--model", default="openai/gpt-4.1",
                       help="GitHub Models model id for idea generation (default: openai/gpt-4.1)")
    ideas.add_argument("--score-model", default="openai/gpt-4.1-mini",
                       help="GitHub Models model id for scoring (default: openai/gpt-4.1-mini)")
    ideas.set_defaults(func=cmd_ideas)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
