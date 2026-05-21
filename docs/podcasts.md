# Podcast transcription

Half the interesting AI signal lives in podcasts. By default the radar
treats podcast feeds the same as any other RSS — it grabs the title,
the link, and the `<description>` field. For a podcast that's usually
a teaser ("This week we sit down with X to talk about Y"), which gives
the scoring model nothing concrete to grip.

Opt-in transcription fixes that. When enabled, the radar:

1. Detects audio enclosures (`<enclosure type="audio/...">`) on each RSS item.
2. For thin-summary podcast items (`<400` chars), downloads the audio and runs it through [`podcast-transcriber`](https://pypi.org/project/podcast-transcriber/).
3. Caches the transcript at `_workdir/transcripts/<sha1(url)>.txt`.
4. Appends the first ~2400 chars to the item's `summary` so the scorer sees real content.

Off by default. Costs time and sometimes money, so you turn it on
deliberately.

## Setup

Pick **one** transcription tier. Each has different cost and quality
tradeoffs.

### Option A: Google Gemini (recommended)

Fast, great diarization, generous free quota.

```bash
pip install "podcast-transcriber[gemini]"
export GOOGLE_API_KEY=...   # from https://aistudio.google.com/app/apikey
```

### Option B: OpenAI Whisper API

About $0.006 per minute. Reliable, no quota worries.

```bash
pip install "podcast-transcriber[openai]"
export OPENAI_API_KEY=...
```

### Option C: Local whisper.cpp

Free, runs on your laptop, slower. Best for batch runs you can leave overnight.

```bash
pip install "podcast-transcriber[local]"
# also needs ffmpeg + a whisper.cpp binary or `pip install openai-whisper`
```

`podcast-transcribe` auto-detects which tier is available based on which
keys/binaries are present.

## Usage

### Per-run (CLI flag)

```bash
python -m radar run --transcribe
```

### Always-on (env var)

In your `.env`:

```
SIGNAL_TRANSCRIBE_PODCASTS=auto
```

Three modes:

| Mode | Behavior |
|------|----------|
| `none` | Skip transcription entirely. Default. |
| `auto` | Transcribe only items where the RSS summary is < 400 chars. |
| `all` | Transcribe every podcast item, even if the summary is rich. |

### Bounded by design

Capped at **5 transcriptions per run**. This is hard-coded so a single
cron run can't surprise-bill you. Tune `max_items` in
`radar/transcribe.py:enrich_with_transcripts` if you want more.

## Caching

Transcripts cache at `_workdir/transcripts/<sha1(audio_url)>.txt`. The
key is the audio URL, so:

- Re-running on the same day → free (cache hit on every item).
- Re-scoring with a different model → free.
- A different episode of the same show → fresh transcription.

Delete `_workdir/transcripts/` to force a full re-transcribe.

## Cost ballpark

Assuming 5 podcast items per day, 45 min average length:

| Tier | Daily cost | Monthly cost |
|------|-----------|-------------|
| Gemini (free quota) | $0 | $0 (until you hit limits) |
| Gemini (paid) | ~$0.20 | ~$6 |
| OpenAI Whisper API | ~$1.35 | ~$40 |
| Local whisper.cpp | $0 | $0 (but uses your CPU/GPU time) |

Defaults stay opt-out so the daily cron Action keeps running on a $0
budget.

## When to skip

- **Your feeds are all written publications**. Then there's nothing to transcribe.
- **You're scoring on title-only signal**. Faster, cheaper, often enough.
- **Daily cron in Actions**. The free-tier Actions minutes are limited and audio download + transcription eats them fast. Run transcription locally on demand instead.

## Troubleshooting

**"podcast-transcribe CLI not on PATH"** — the package didn't install
its entry point. Run `pip show podcast-transcriber` to confirm install,
then `which podcast-transcribe` (or `where.exe podcast-transcribe` on Windows).

**Timeout after 10 minutes** — long episode + slow tier. Either switch
to Gemini, or bump `timeout_s` in `radar/transcribe.py:_transcribe_one`.

**Transcripts are empty** — the audio URL might be DRM'd (Spotify
originals, Apple+ exclusives) or behind auth. `podcast-transcriber`
handles open RSS audio enclosures. Walled content stays walled.
