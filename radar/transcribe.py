"""Optional podcast transcription enrichment.

When an RSS feed serves podcasts, the <description> is often a teaser
("This week we talk to X about Y"). That gives the scorer nothing to grip.
This module shells out to the `podcast-transcriber` PyPI package to get
the actual transcript and uses it to enrich the item's summary before
scoring.

Off by default. Enable per run with `--transcribe` on `python -m radar run`
or by setting `SIGNAL_TRANSCRIBE_PODCASTS=auto` in the env.

Modes:
  none  - skip entirely (default)
  auto  - transcribe only items where summary is thin (< 400 chars)
  all   - transcribe every podcast item

Requires (install separately):
  pip install "podcast-transcriber[openai]"   # uses OpenAI Whisper API
  pip install "podcast-transcriber[gemini]"   # uses Google Gemini
  pip install "podcast-transcriber[local]"    # uses local whisper.cpp

Plus the matching env var:
  OPENAI_API_KEY   (for [openai])
  GOOGLE_API_KEY   (for [gemini])

Transcripts are cached at `_workdir/transcripts/<sha1(url)>.txt`, so a
re-run never re-pays for the same episode.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_THIN_SUMMARY_THRESHOLD = 400
_TRANSCRIPT_BUDGET_CHARS = 2400  # cap appended transcript so prompts stay sane


def _cache_path(audio_url: str, cache_dir: Path) -> Path:
    digest = hashlib.sha1(audio_url.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}.txt"


def _have_transcriber() -> bool:
    return shutil.which("podcast-transcribe") is not None


def _transcribe_one(audio_url: str, cache_dir: Path, timeout_s: int = 600) -> str | None:
    """Return transcript text for an audio URL, using cache when available."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(audio_url, cache_dir)
    if cached.exists() and cached.stat().st_size > 0:
        return cached.read_text(encoding="utf-8")

    if not _have_transcriber():
        log.warning("podcast-transcribe CLI not on PATH; skip transcription")
        return None

    try:
        proc = subprocess.run(
            ["podcast-transcribe", audio_url, "--format", "text"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log.warning(f"transcription timeout for {audio_url}")
        return None
    except FileNotFoundError:
        log.warning("podcast-transcribe CLI not found")
        return None

    if proc.returncode != 0:
        log.warning(f"podcast-transcribe failed (code {proc.returncode}): "
                    f"{(proc.stderr or '').strip()[:300]}")
        return None

    text = (proc.stdout or "").strip()
    if not text:
        return None
    cached.write_text(text, encoding="utf-8")
    return text


def _resolve_mode(cli_flag: bool | None) -> str:
    """CLI flag wins over env var. Returns one of: none, auto, all."""
    if cli_flag:
        # --transcribe with no value defaults to auto
        env_val = (os.environ.get("SIGNAL_TRANSCRIBE_PODCASTS") or "auto").lower()
        return env_val if env_val in {"auto", "all"} else "auto"
    env_val = (os.environ.get("SIGNAL_TRANSCRIBE_PODCASTS") or "none").lower()
    return env_val if env_val in {"none", "auto", "all"} else "none"


def enrich_with_transcripts(items: list[dict], workdir: Path,
                            *, mode: str = "auto",
                            max_items: int = 5) -> list[dict]:
    """Append transcript snippets to podcast items' summary field.

    Mutates and returns the same list. Bounded by `max_items` so a single
    run can't accidentally transcribe an entire feed.
    """
    if mode == "none":
        return items

    cache_dir = workdir / "transcripts"
    transcribed = 0

    for it in items:
        if transcribed >= max_items:
            break
        audio_url = (it.get("audio_url") or "").strip()
        if not audio_url:
            continue
        summary_len = len(it.get("summary") or "")
        if mode == "auto" and summary_len >= _THIN_SUMMARY_THRESHOLD:
            continue

        log.info(f"transcribing podcast: {it.get('title', '?')[:60]}")
        text = _transcribe_one(audio_url, cache_dir)
        if not text:
            continue

        snippet = text[:_TRANSCRIPT_BUDGET_CHARS].strip()
        if len(text) > _TRANSCRIPT_BUDGET_CHARS:
            snippet += "..."
        joiner = "\n\n[transcript excerpt]\n" if (it.get("summary") or "").strip() else "[transcript excerpt]\n"
        it["summary"] = ((it.get("summary") or "") + joiner + snippet).strip()
        transcribed += 1

    if transcribed:
        log.info(f"transcribed {transcribed} podcast item(s)")
    return items
