```
    ·  ·  ·  ·  ·                       ·   ·
  ·              ·                   ·          ·
 ·    ((•))       ·    signal       ·   post    ·
  ·              ·     engine        ·          ·
    ·  ·  ·  ·  ·                       ·   ·
            ╲                                   ╱
             ╲    feeds → score → idea →    ╱
              ╲           polish           ╱
               ╲_________________________╱
```

# signal-engine

**Stop posting like a default LLM.**

Your LinkedIn is showing. The "Excited to share" openers. The rule-of-three closers. The em dash addiction. Every founder's feed reads like the same model with a different headshot. Readers can smell it. You can probably smell your own posts.

This repo is the opposite. A personal content radar that scouts YOUR feeds, scores items against YOUR editorial scope, drafts in YOUR voice, and pushes the polished post straight into your LinkedIn drafts tab.

You stay the author. The LLM does the boring matching work in between.

## What you get

- 🛰️ **Daily radar** — pulls your RSS + podcast feeds at 06:30 UTC, scores items 1-10 for content potential against your editorial scope, commits a digest to `digests/raw/`.
- 🃏 **Weekly idea cards** — Monday morning, the engine generates 3-5 idea cards for your week's writing, each anchored to one editorial track and one of your real stories.
- 🎨 **Polish skill** — Copilot CLI command turns one card into a 900-1200 char post in your voice, plus a matching image, plus optional video.
- 🚀 **Drafts push** — one more command shoves the finished post straight into your LinkedIn drafts. You tap publish from the real LinkedIn composer. No copy-paste. No formatting loss.

## What this is vs what it isn't

| What this is | What this is NOT |
|--------------|------------------|
| Personal radar with your taste baked in | A "post this for me" autopilot |
| Your stories, your voice, your scope | Generic AI thought leadership generator |
| $0 scoring loop (GitHub Models, free for public repos) | Yet another SaaS subscription |
| 30 min to set up, hackable in 30 min more | A black-box pipeline you can't tune |
| You ship the post yourself | A bot that posts at 7am while you sleep |

Founders ship founder thoughts. Not LLM thoughts.

## How fast

```
clone → 30 min → first scored digest committed by GitHub Actions
config → 5 min   → tracks, scope, stories, voice
write  → 5 min   → polish one card into a finished post + image
push   → 10 sec  → linkedin_post.py drops it in your drafts
```

That's it. The rest is iteration.

## How it works

```
       ┌─────────────────────┐
       │  sources.yaml       │  Your RSS + podcast feeds, weighted.
       └─────────┬───────────┘
                 │
                 ▼
       ┌─────────────────────┐
       │  radar/fetch.py     │  Pulls items, dedupes, caps per feed.
       └─────────┬───────────┘
                 │
                 ▼
       ┌─────────────────────┐    ┌────────────────────────────────┐
       │  radar/score.py     │◄───┤ content-plan.editorial_scope   │
       │  (GitHub Models)    │    │  "what I cover, who I write    │
       │                     │    │   for, what's out of scope"    │
       └─────────┬───────────┘    └────────────────────────────────┘
                 │
                 ▼
       ┌─────────────────────┐
       │ digests/raw/        │  Daily archive, committed by Actions.
       │ YYYY-MM-DD.md       │
       └─────────┬───────────┘
                 │  (weekly aggregation, Monday morning)
                 ▼
       ┌─────────────────────┐    ┌─────────────────────┐
       │ radar/ideas.py      │◄───┤ stories.yaml        │
       │ (GitHub Models)     │◄───┤ tracks (themes)     │
       └─────────┬───────────┘    └─────────────────────┘
                 │
                 ▼
       ┌─────────────────────┐
       │ digests/YYYY-WW.md  │  3-5 idea cards for your week.
       └─────────┬───────────┘
                 │
                 ▼
       ┌─────────────────────┐    ┌─────────────────────┐
       │ signal-polish       │◄───┤ voice-profile.md    │
       │ (Copilot CLI skill) │    │  your voice rules   │
       └─────────┬───────────┘    └─────────────────────┘
                 │
                 ▼
       ┌─────────────────────┐
       │ _workdir/posts/     │  Finished post + image (+ video).
       │ <slug>.md           │
       └─────────┬───────────┘
                 │  optional: one more command
                 ▼
       ┌─────────────────────┐
       │ scripts/            │  POSTs via LinkedIn REST API
       │ linkedin_post.py    │  → lifecycleState: DRAFT
       └─────────┬───────────┘
                 │
                 ▼
       ╭─────────────────────╮
       │   📱 LinkedIn drafts  │  Open the app, tap publish.
       ╰─────────────────────╯
```

## What's in the repo

```
content-plan.yaml         # Editorial scope and tracks (THE most important config)
sources.yaml              # RSS and podcast feeds with weights
stories.yaml              # Your lived examples (post fuel)
voice-profile.example.md  # Voice rules template (copy → voice-profile.md, edit)

radar/                    # Stage 1: Python scout + scoring engine
  cli.py                  # `python -m radar run` / `python -m radar ideas`
  fetch.py                # RSS fetcher
  score.py                # GitHub Models scoring (free, batched, JSON in/out)
  ideas.py                # Weekly idea-card generator
  digest.py               # Markdown rendering

prompts/                  # Prompts the scoring and ideas models see
  score_system.md         # Generic, parameterized with {editorial_scope}
  ideas_system.md         # Idea-card generation rules
  image_prompts.md        # Image-code library the polish skill looks up

scripts/                  # Optional glue (all gated on env vars)
  generate_image.py       # OpenAI gpt-image-2 (~$0.20/image)
  generate_video.py       # Replicate Seedance / Kling Omni (~$1-2/clip)
  linkedin_auth.py        # One-time OAuth handshake (token good for 60 days)
  linkedin_post.py        # Push polished post → LinkedIn drafts (or publish live)

.copilot/skills/
  signal-polish/SKILL.md  # Stage 2: turn one card into a finished post

.github/workflows/
  radar.yml               # Daily cron (weekdays 06:30 UTC)
  ideas.yml               # Weekly cron (Monday 06:00 UTC)
```

## Get started

→ See [QUICKSTART.md](QUICKSTART.md). 30 minutes from clone to first commit.

## Customization is the whole point

Three files make this YOUR engine instead of someone else's:

1. **`content-plan.yaml`** — your editorial scope. The more specific you are, the better the scoring. Vague scope, vague scores. "I write about AI" is useless. "I write tactical patterns for B2B SaaS founders shipping AI features, with skepticism toward enterprise AI hype" — now we're talking.
2. **`sources.yaml`** — feeds you trust. Drop the ones you don't read. Add the niche newsletter your competitors don't know about. Boost the weight on signal sources, drop it on noise sources.
3. **`stories.yaml`** — your real shipped work. The thing that makes your posts not interchangeable with anyone else's. 3-10 stories is enough to start.

Optional but high-leverage:
- **`voice-profile.md`** — copy from `voice-profile.example.md` and tune. Banned phrases (kill "leverage", "delve", "groundbreaking"). Structural rules (vary sentence length, no triplets). Required moves (a mid-paragraph question, a self-mocking aside). The more opinionated, the more it sounds like you.

Don't touch the Python or the prompts unless you want to. The four config files above adapt the engine to your voice.

## Track posts on a board (optional)

The radar gives you idea cards. The polish skill turns them into posts. To track the queue between "this is an idea" and "this is live" — a small GitHub Project board works well and stays inside GitHub.

→ See [docs/board-pattern.md](docs/board-pattern.md) for the columns, fields, and setup. Five minutes to build.

## Optional features

| Feature | Requires | Cost | Default |
|---------|----------|------|---------|
| Daily scoring | `GITHUB_TOKEN` (free for public repos) | $0 | ON |
| Weekly idea cards | `GITHUB_TOKEN` | $0 | ON |
| Polished posts | Copilot CLI | $0 (already part of GitHub) | ON |
| Image generation | `OPENAI_API_KEY` | ~$0.20 / image | OFF (turns on when key is set) |
| Video generation | `REPLICATE_API_TOKEN` | ~$1-2 / clip | OFF |
| LinkedIn drafts push | LinkedIn Dev App + OAuth | $0 | OFF |

You can run the scoring loop forever for $0. Everything else is opt-in.

## License

MIT. Fork it. Strip it. Ship it. Call it your own. No attribution required.

## Origin story

Built by [@JW-Sthlm](https://github.com/JW-Sthlm) ([Johan on LinkedIn](https://www.linkedin.com/in/johanwallquist/)) as a personal content engine while running partner-facing work at Microsoft. Open-sourced to the Founder Days 2026 cohort the night before the closing panel because watching 20 founders ship agentic sales tools and then publish "Excited to announce" posts felt like a contradiction.

You're an AI-first startup. Your content stack should be too.

PRs welcome. Issues welcome. Forks especially welcome.
