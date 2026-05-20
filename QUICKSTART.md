# Quickstart

Get the engine running in under 30 minutes. No prior Python or GitHub Actions experience required.

## What you'll have at the end

- A daily cron that fetches your favorite RSS feeds, scores items for content potential against your editorial scope, and commits a digest to `digests/raw/`.
- A weekly cron that turns the highest-scoring items into idea cards in `digests/YYYY-WW.md`.
- A polish skill you invoke from Copilot CLI that turns one idea card into a publish-ready post (plus optional image and video).
- Total cost: $0 for scoring (GitHub Models), optional spend for images/video.

## Prerequisites

- A GitHub account.
- (Optional) Python 3.11+ locally if you want to run the CLI on your own machine. The cron runs entirely in GitHub Actions so this is not required.
- (Optional) An OPENAI_API_KEY if you want image generation.
- (Optional) A REPLICATE_API_TOKEN if you want video generation.

## Step 1: Use as a template

Click **Use this template** at the top of the repo on GitHub. Create your own copy. Make it **public** (GitHub Models is free for public repos and works without extra setup).

If you'd rather fork instead of templating, that works too.

## Step 2: Edit `content-plan.yaml`

Open `content-plan.yaml` and rewrite the `editorial_scope` block to describe:

- Who you write for
- What topics you cover
- What you DON'T cover

Then edit the `tracks` list — these are the recurring themes the engine will generate idea cards against.

The more specific you are, the better the scoring works. Vague scope = vague scores.

## Step 3: Edit `sources.yaml`

Replace or extend the example RSS feeds with the ones you actually read. Don't include feeds you don't trust — noise in, noise out.

Each feed gets a `weight` (default 1.0). Bump weights up for sources you value most. Drop weights to 0.7-0.8 for sources you keep but want dampened.

## Step 4: Edit `stories.yaml`

Add 3-10 real things you've done. The engine plugs these in as "fuel" so your posts feel concrete instead of generic. Even rough drafts are fine — better to have something than nothing.

## Step 5: Copy and edit the voice profile

```
cp voice-profile.example.md voice-profile.md
```

Edit `voice-profile.md` to capture your voice. Banned phrases, structural rules, required moves. The polish skill reads this every time it generates a post.

## Step 6: Commit and push

```
git add .
git commit -m "Configure my signal-engine"
git push
```

## Step 7: Watch the first run

Go to your repo's **Actions** tab on GitHub. Find the **Signal daily radar** workflow. Click **Run workflow** to trigger it manually (don't wait for tomorrow morning).

If everything is wired correctly:
- The job runs for 30-90 seconds
- It commits a new file at `digests/raw/YYYY-MM-DD.md`
- That file has scored items from your feeds

If it fails, check the Actions log. The most common issues are:
- A bad URL in `sources.yaml` (the run still continues, but you'll see warnings)
- GitHub Models not enabled (rare, public repos get it by default)
- A typo in `content-plan.yaml` (yaml is strict about indentation)

## Step 8: Run the weekly idea generator

In **Actions**, find **Signal weekly ideas** and click **Run workflow**. This pulls a week's worth of items, scores them, and generates idea cards. Output lands at `digests/YYYY-WW.md`.

If you don't have a week of history yet, the digest will be slim. That's fine. The cron runs every Monday morning and will fill out over time.

## Step 9: Polish an idea card

Open Copilot CLI in this repo and say:

```
polish this week's signal
```

The `signal-polish` skill walks you through picking an idea card, generates the post, and writes it to `_workdir/posts/`. If you set `OPENAI_API_KEY`, it also generates a matching image.

Edit the post in your editor, paste it to LinkedIn, ship.

## Step 10: Iterate

The first week's idea cards will be okay but not great. The engine learns your voice as you:

- Add more stories to `stories.yaml`
- Tighten the editorial scope as you see what scores well and what doesn't
- Refine `voice-profile.md` after the first few drafts to capture moves the polish skill is missing or overdoing
- Adjust source weights based on which feeds produce usable signal

## Local development (optional)

If you want to run the CLI on your own machine:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# Set your GitHub token (used for GitHub Models scoring)
export GITHUB_TOKEN=$(gh auth token)

# Daily run
python -m radar run --dry-run

# Weekly ideas
python -m radar ideas --dry-run
```

`--dry-run` prints to stdout instead of writing files. Drop the flag to save normally.

## Optional: enable image generation

1. Get an OpenAI API key from https://platform.openai.com/api-keys
2. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`
3. The polish skill will pick it up automatically. Image cost runs about $0.20 per post at high quality.

## Optional: enable video generation

1. Get a Replicate API token from https://replicate.com/account/api-tokens
2. Add `REPLICATE_API_TOKEN` to your `.env`
3. Ask the polish skill for a video: "polish this week's signal with video"
4. Cheap preset (Seedance) runs ~$1 per 10-second clip. Premium (Kling Omni) runs ~$2.20 per 8-second clip.

## Optional: push polished posts to LinkedIn drafts

Closes the loop — the polished post lands in your LinkedIn drafts tab, you review and one-click publish from LinkedIn's real composer. No copy-paste, no risk of pushing a typo.

**One-time setup:**

1. Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps
2. Under **Auth** → add redirect URL: `http://localhost:8765/callback`
3. Under **Products** → request:
   - "Sign In with LinkedIn using OpenID Connect"
   - "Share on LinkedIn"
   (Both auto-approve usually within minutes.)
4. Copy your Client ID and Client Secret from the **Auth** tab into `.env`:
   ```
   LINKEDIN_CLIENT_ID=...
   LINKEDIN_CLIENT_SECRET=...
   ```
5. Run the auth helper once:
   ```
   python scripts/linkedin_auth.py
   ```
   Browser opens, you authorize, the script captures the redirect, fetches your access token + author URN, and writes both to `.env`.

Tokens expire every 60 days. Re-run `linkedin_auth.py` when `linkedin_post.py` starts failing with 401.

**Usage:**

After polishing a post, ask the skill: `push to LinkedIn` (or any of "save as draft", "send to drafts"). The skill runs:

```
python scripts/linkedin_post.py --post _workdir/posts/<slug>.md --image _workdir/images/<slug>.png
```

The post lands in your LinkedIn drafts. Open LinkedIn → click **Start a post** → click the **View drafts** link in the composer. It's there, ready to review.

Add `--publish` to skip drafts and go live immediately (default is drafts for safety).

## Troubleshooting

**The daily run produces empty digests.**
Your `score_threshold` is too high or your feeds are too narrow. Lower the threshold in `sources.yaml` `defaults`, or add more feeds.

**Idea cards feel off.**
Your `editorial_scope` is too generic. Make it more specific. Name actual topics, name your audience, name what you DON'T cover.

**Posts sound like AI.**
Your `voice-profile.md` doesn't have enough specifics. Add banned phrases. Add structural rules. List voice anchors. The polish skill only knows what you tell it.

**Image generation costs are higher than expected.**
You're probably running at `--quality high` on every generation. Drop to `medium` or `low` in `prompts/image_prompts.md` if you don't need the absolute best.
