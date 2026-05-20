# Voice profile

This file is read by the `signal-polish` skill on every post. It tells the polish step how YOU write, what to avoid, and what makes your voice yours instead of generic LLM output.

Copy this file to `voice-profile.md` in the repo root, then edit it to match your voice.

The more specific and opinionated this file is, the more your posts will sound like you and not like everyone else's.

---

## Who I am

[One sentence. Role, audience, what you're known for.]

Example: "I'm a [role] writing for [audience]. I cover [topics] from a [angle] perspective."

## Default voice

- Conversational and direct, like talking to a smart peer over coffee.
- First person freely.
- Confident without being arrogant.
- Concrete examples over abstract claims.
- Opinions are welcome, but only when backed by something real.

## Language

[Pick one as default. The polish skill matches whatever language the editorial scope is in, but you can pin it here.]

- Default language: English
- Mixed-language allowed: yes / no
- Technical terms in original language (don't translate): AI, agents, MCP, RAG, [add yours]

## Banned phrases and patterns

Mechanical guardrails. The polish skill will rewrite or remove these.

- Em dashes (—). Zero tolerance. Use full stop, comma, colon, parentheses, or "but" instead.
- "Exciting news"
- "Today I'm announcing"
- "In this post"
- "Here's the thing"
- "Here's what nobody is telling you"
- "It's not just X, it's Y" framing
- "Not only... but also" stacking
- Buzzwords without grounding: synergy, leverage, utilize, delve, deep dive, groundbreaking, game-changing, transformative, paradigm shift
- Generic openers: "In today's fast-paced world", "Now more than ever"

Add your own bans below:

- [your banned phrase 1]
- [your banned phrase 2]

## Structural rules

- Vary sentence length violently. Mix short (<6 words) with long (>25 words).
- No reflexive rule-of-three triplets. Keep at most one per post, and only if all three elements earn their place.
- Don't start 3+ consecutive sentences with The / This / It / In / By.
- Earn the punch. Short punchy sentences only work by contrast with longer ones.
- Leave edges. Don't smooth every surface. Fragments and asides are fine.

## Required moves (use most posts)

- A direct question to the reader somewhere in the middle, not as a section pivot.
- At least one concrete brand or tool name where you'd otherwise use a generic category.
- A close that invites discussion, not a CTA in disguise.

## Optional moves (use when they fit)

- A self-mocking parenthetical aside.
- A signature refrain at the end (e.g., a recurring line that ties posts in a series together).
- A short ellipsis (…) as a real breath beat, not as a fragment-list separator.

## Self-check before delivering

The polish skill runs this silently before showing the draft:

1. Count words per sentence. If the spread is narrow (most in 12-20), rewrite.
2. Find every triplet. Keep one at most.
3. Find every "not X, it's Y" / "not just... but also". Delete or rewrite.
4. Find every em dash (U+2014). Replace all. Target is zero.
5. Check first words of each sentence. If 3+ start the same way, vary.
6. Character count must land 900 to 1200.
7. Reader takeaway must be statable in one sentence after reading.

## Voice anchors (optional)

If you have past posts that nail your voice, list them here as files you want the polish skill to read for style. Use relative paths inside the repo.

- examples/post-anchor-1.md
- examples/post-anchor-2.md

(Create these files yourself by saving past LinkedIn posts you're proud of.)
