---
name: signal-polish
description: Polish a Signal idea card into a LinkedIn-ready post (plus optional image and video) in your voice. Reads weekly idea cards from `digests/YYYY-WW.md` (or the raw daily archive), applies the voice profile in `voice-profile.md`, and writes the finished post to `_workdir/posts/`. Triggers on phrases like "polish this week's signal", "make a LinkedIn post from this week's ideas", "polish idea N from the signal", "signal polish".
---

# signal-polish

Stage 2 of the signal-engine pipeline. Reads a weekly idea-card digest (`digests/YYYY-WW.md`) and turns one card into a publish-ready post plus an optional matching image and video.

Stage 1 (the Python CLI in `radar/`) does the daily and weekly fetch + score + idea generation. This skill is what turns one of those idea cards into actual content you can publish.

## When to invoke

Trigger phrases (any language):
- "polish this week's signal"
- "polish idea 3 from this week's signal"
- "make a LinkedIn post from this week's signal"
- "signal polish"

## Inputs

- **Digest file**, defaults to the current ISO-week file `digests/YYYY-WW.md`. If "yesterday's raw" or a specific date is given, use `digests/raw/YYYY-MM-DD.md` instead.
- **Idea index**, integer 1..N from the Summary table. If unspecified, present the table via `ask_user` and let the user pick.
- **Tone variant** (optional), defaults to whatever the card's `format` field says.
- **Image**, default yes. Skip if user says "no image" / "skip image" / "text only".
- **Video**, default no. Activate only if user says "with video" / "animate" / "video too".

## Steps

### 1. Locate the digest

Find the requested file in `digests/` (weekly) or `digests/raw/` (daily). If missing, list the 5 most recent and ask the user to pick.

### 2. Parse cards

For a weekly digest, extract idea cards with fields: index, track, title, hook, format, partner_takeaway, image_code, story_ref, source_refs (with titles/urls), reasoning.

For a raw daily digest, parse items: index, title, source, score, url, score_reason, partner_takeaway, partner_summary.

### 3. Pick the card

If the user named an idea or topic, match it. Otherwise present a numbered list via `ask_user` (single-select). "The highest" picks rank 1.

### 4. Pull fuel

- If `story_ref` is set, open `stories.yaml` and read the matching story. Use the `summary` and `learned` fields as primary substance.
- If `source_refs` are set, summaries are already in the card. Use them as supporting evidence, not the main story.
- The `partner_takeaway` field is the anchor of the post. The reader must walk away with that exact takeaway.

### 5. Load voice profile

Read `voice-profile.md` from the repo root. This is the user's voice rules:
- Banned phrases and patterns
- Language and tone
- Sentence-length rhythm
- Structural moves they want or want to avoid
- Self-check rules

If `voice-profile.md` does not exist, fall back to `voice-profile.example.md` and tell the user inline that they should copy and customize the example.

### 6. Draft

Write a post for the chosen card. **Hard rules** (override these in `voice-profile.md` if you want):

- Length: 900 to 1200 characters (count, including hashtags).
- Structure:
  - Opening: a sharp observation, concrete fact, or unexpected angle. Use the card's `hook` as a seed, do not paste it verbatim. Never open with "Exciting news", "Today I'm announcing", "In this post", or similar throat-clearing.
  - 2 to 3 short paragraphs of substance: what happened or what you did, why your audience should care, what they should take away. The takeaway must be explicit and concrete.
  - One genuine closing question that invites discussion.
  - 4 to 5 hashtags on their own line, last.
- Apply every rule from `voice-profile.md`.

### 7. Self-check (silent revision pass)

Before showing the draft, run the structural self-check from `voice-profile.md`. At minimum:

1. Sentence-length spread. If most are 12 to 20 words, rewrite to add variation.
2. No reflexive triplets. Keep at most one per post.
3. No "not X, it's Y" framing.
4. No em dashes (the U+2014 character). Replace every one. Target is zero.
5. Sentence-opener variety. No 3+ consecutive sentences starting with the same word.
6. Character count, must land 900 to 1200. Adjust.
7. Reader takeaway. Can a reader state it in one sentence after reading? If not, rewrite.

### 8. Generate image (default: on)

Skip only if user explicitly says "no image" / "skip image" / "text only". Requires `OPENAI_API_KEY` to be set in the environment. If not set, log inline and continue without an image (do not fail the whole flow).

Read `prompts/image_prompts.md` and find the `image_code` from the chosen card. Use that prompt as the base, then add 1-2 visual elements tied to the specific post's hook or takeaway.

Write the expanded prompt to `_workdir/images/<slug>.prompt.txt` (create the folder if missing). Output path for the PNG: `_workdir/images/<slug>.png`.

Run the image generator:

```powershell
python scripts/generate_image.py `
  --prompt-file "_workdir/images/<slug>.prompt.txt" `
  --out "_workdir/images/<slug>.png" `
  --no-composite `
  --size 1024x1024 --quality high
```

For portrait-led codes, add `--portrait <path>` instead of `--no-composite` and point it at your reference photo.

If the script exits non-zero, retry once. If it still fails, report inline and continue without an image.

### 8b. Generate video (default: off)

Activate only when the user explicitly asks for a video (e.g., "with video", "animate this", "video too"). Requires `REPLICATE_API_TOKEN` to be set. If not set, log inline and continue without video.

When activated:

1. The image must already exist on disk from step 8.
2. Build a short motion prompt (1-3 sentences) from the post substance and the image style:

   ```
   Subtle cinematic motion. <Subject>: <small natural movement>. <Background>: <ambient motion>. Camera: <slow dolly-in / static / slow pan>. Mood: <one word from the post>. Square 1:1, no on-screen text, no captions, no logos.
   ```

3. Write the motion prompt to `_workdir/videos/<slug>.motion.txt`.
4. Output path: `_workdir/videos/<slug>.mp4`.
5. Run the video generator:

   ```powershell
   python scripts/generate_video.py `
     --prompt-file "_workdir/videos/<slug>.motion.txt" `
     --start-image "_workdir/images/<slug>.png" `
     --out "_workdir/videos/<slug>.mp4" `
     --quality cheap --aspect-ratio 1:1 --audio
   ```

6. Render time is typically 2-3 minutes (cheap) or 3-5 minutes (premium).
7. On failure: one retry, then continue without video.

### 9. Write post.md and present in chat

Write the polished post to `_workdir/posts/<slug>.md` (create the folder if missing). UTF-8, no BOM, body only (no front matter, no headings — the file body is what gets pasted to LinkedIn verbatim).

Then show the polished post inline in chat for review, with a small footer:

```
Char count: <N>
Sentence-length range: <min> to <max> words
Source: digests/<file> idea <i>, <title>
Track: <id>
Reader takeaway: <one sentence>
Post: <relative path to post.md>
Image: <relative path to png>   (if generated)
Video: <relative path to mp4>   (if generated)
```

### 10. Iterate or accept

If the user asks for revisions, apply them and re-run steps 7 and 9. Don't rerun image generation unless they specifically ask for a new image.

### 11. Push to LinkedIn drafts (optional)

If the user says "push to LinkedIn" / "send to drafts" / "save as draft" / "publish" (or the equivalent in any language), pipe the final post to LinkedIn's Posts API via `scripts/linkedin_post.py`.

**Default lifecycle is DRAFT.** The post lands in the user's LinkedIn drafts tab where they review and one-click publish from the real LinkedIn composer. Switch to `--publish` only if the user explicitly says "publish live" / "go live" / "publish for real".

Requires `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_AUTHOR_URN` in the environment (set up via `scripts/linkedin_auth.py` once per 60 days). If either is missing, tell the user inline and skip — do not fail the whole flow.

Run via the powershell tool:

```powershell
python scripts/linkedin_post.py `
  --post "_workdir/posts/<slug>.md" `
  --image "_workdir/images/<slug>.png" `
  --alt "<short alt text from the image_code description>"
```

Drop `--image` if no image was generated. Add `--publish` to skip drafts and go live.

On success, report the post URN inline and how to find the result in LinkedIn:
- DRAFT: tell the user to open LinkedIn, click "Start a post", then click the "View drafts" link in the composer
- PUBLISHED: tell the user to open `https://www.linkedin.com/feed/`

On 401 / 403: tell the user to re-run `python scripts/linkedin_auth.py` (token expired) and continue. Do not retry automatically.

## File layout (created by this skill)

```
_workdir/
  posts/
    <slug>.md           # the final post body
  images/
    <slug>.prompt.txt   # the image prompt used
    <slug>.png          # the generated image
  videos/
    <slug>.motion.txt   # the video motion prompt
    <slug>.mp4          # the generated video
```

`<slug>` is a short kebab-case identifier built from the post title (lowercase, ASCII, hyphens, max 50 chars).

## Notes

- This skill is intentionally simple. No multi-agent orchestration, no sub-skills, no humanizer chains. If you want more sophistication, fork it.
- The voice rules live in `voice-profile.md` so users can customize without editing this skill. Treat that file as the source of truth for tone, language, banned phrases, and structural moves.
- Image and video generation are both optional and gated on env vars. The skill should produce a usable post even with neither set.
