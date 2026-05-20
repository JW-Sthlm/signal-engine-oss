# signal-engine

A content opportunity engine for solo creators and small teams. It scouts your RSS feeds and podcasts, scores items against your editorial scope, generates weekly idea cards, and helps you polish a chosen card into a publish-ready post.

Built around two simple stages:

1. **Scout + score (Python, runs in GitHub Actions).** Daily cron fetches feeds, scores items for content potential against YOUR editorial scope, commits a digest. Weekly cron turns the best items into idea cards.
2. **Polish (Copilot CLI skill).** You pick a card, the skill drafts a post in your voice (defined in `voice-profile.md`), generates a matching image, optionally an animated video.

Free to run for the scoring loop. GitHub Models gives you free LLM scoring with your normal GitHub token. Optional API keys unlock image and video generation.

## Why this exists

Most "AI content tools" generate generic posts that sound like everyone else. This engine flips that: it's a personal radar that knows YOUR topics, YOUR voice, YOUR stories. The LLM does the boring matching work. You stay the author.

## What you get

- A daily digest of items worth your attention (`digests/raw/YYYY-MM-DD.md`)
- A weekly batch of idea cards with hooks, takeaways, story matches, and image briefs (`digests/YYYY-WW.md`)
- A polish flow that turns one card into a finished post in your voice
- Optional image generation via OpenAI (gpt-image-2)
- Optional video generation via Replicate (Seedance, Kling Omni)

## How fast does this go?

- 30 minutes to clone, configure, and trigger the first run (see [QUICKSTART.md](QUICKSTART.md))
- 5 minutes to polish an idea card into a finished post once the engine is running
- $0 for the scoring loop on a public repo (GitHub Models is free)
- ~$0.20 per image, ~$1 per 10-second video (only when you want them)

## How it works

```
       ┌───────────────────┐
       │  sources.yaml     │  Your RSS + podcast feeds, weighted.
       └────────┬──────────┘
                │
                ▼
       ┌───────────────────┐
       │  radar/fetch.py   │  Pulls items, dedupes, caps per feed.
       └────────┬──────────┘
                │
                ▼
       ┌───────────────────┐    ┌─────────────────────────────┐
       │  radar/score.py   │◄───┤ content-plan.editorial_scope│
       └────────┬──────────┘    └─────────────────────────────┘
                │
                ▼
       ┌───────────────────┐
       │ digests/raw/      │  Daily scored archive (committed by Actions).
       │ YYYY-MM-DD.md     │
       └────────┬──────────┘
                │  (weekly aggregation)
                ▼
       ┌───────────────────┐    ┌──────────────────────┐
       │ radar/ideas.py    │◄───┤ stories.yaml         │
       │                   │◄───┤ content-plan.tracks  │
       └────────┬──────────┘    └──────────────────────┘
                │
                ▼
       ┌───────────────────┐
       │ digests/YYYY-WW.md│  Weekly idea cards (committed by Actions).
       └────────┬──────────┘
                │
                ▼
       ┌───────────────────┐    ┌──────────────────────┐
       │ signal-polish     │◄───┤ voice-profile.md     │
       │ (Copilot CLI)     │◄───┤ prompts/image_prompts│
       └────────┬──────────┘    └──────────────────────┘
                │
                ▼
       ┌───────────────────┐
       │ _workdir/posts/   │  Finished post you copy to LinkedIn.
       │ <slug>.md         │  (Plus optional image and video.)
       └───────────────────┘
```

## What's in this repo

```
content-plan.yaml         # Editorial scope and tracks (the core config)
sources.yaml              # RSS and podcast feeds with weights
stories.yaml              # Your lived examples (post fuel)
voice-profile.example.md  # Voice rules template (copy to voice-profile.md)

radar/                    # Stage 1: Python scout + scoring engine
  cli.py                  # `python -m radar run` and `python -m radar ideas`
  fetch.py                # RSS fetcher with feed dedup and per-source caps
  score.py                # GitHub Models scoring with batched JSON in/out
  ideas.py                # Weekly idea-card generator
  digest.py               # Markdown rendering for daily and weekly digests

prompts/                  # System and user prompts for scoring and ideas
  score_system.md         # Generic, parameterized with {editorial_scope}
  score_user.md
  ideas_system.md
  ideas_user.md
  image_prompts.md        # Reusable image codes the polish skill looks up

scripts/                  # Optional generators (gated on env vars)
  generate_image.py       # OpenAI gpt-image-2 wrapper
  generate_video.py       # Replicate wrapper (Seedance / Kling Omni)

.copilot/skills/
  signal-polish/SKILL.md  # Stage 2: turn one idea card into a finished post

.github/workflows/
  radar.yml               # Daily cron, runs `python -m radar run`
  ideas.yml               # Weekly cron, runs `python -m radar ideas`

digests/                  # Generated. Daily scored items + weekly idea cards.
_workdir/                 # Generated. Local cache + posts + images + videos.
```

## Get started

See [QUICKSTART.md](QUICKSTART.md). 30 minutes from clone to first digest.

## Customization

Everything that makes your engine YOURS lives in three files:

- **`content-plan.yaml`** — what topics matter, what audience you write for, what's out of scope
- **`sources.yaml`** — what feeds you trust
- **`stories.yaml`** — your real examples that make posts unique to you

Plus one optional but high-leverage file:

- **`voice-profile.md`** — copy from `voice-profile.example.md` and tune until posts sound like you

The Python code, the prompts, the image library, the workflow scheduling — all of that you can leave alone. Tune the four config files above and the engine adapts.

## Optional features

| Feature | Requires | Cost |
|---------|----------|------|
| Daily scoring | GITHUB_TOKEN (free) | $0 |
| Weekly idea cards | GITHUB_TOKEN (free) | $0 |
| Polished posts | Copilot CLI | $0 (already part of your GitHub) |
| Image generation | OPENAI_API_KEY | ~$0.20 per image |
| Video generation | REPLICATE_API_TOKEN | ~$1 per 10s clip |

You can run the scoring loop forever for $0. Image and video are off by default.

## License

MIT. See [LICENSE](LICENSE).

## Origin

Built by [Johan Wallquist](https://www.linkedin.com/in/johanwallquist/) as a personal content engine while running partner-facing work at Microsoft. Released to the Founder Days 2026 cohort and anyone else who wants to stop posting like a default LLM. Pull requests welcome.
