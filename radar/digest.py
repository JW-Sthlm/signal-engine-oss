"""Build markdown digests. Two formats: daily raw archive and weekly idea cards."""
from __future__ import annotations


def _tag_chip(tags: list[str]) -> str:
    if not tags:
        return ""
    return " ".join(f"`{t}`" for t in tags)


def build_digest(items: list[dict], today: str, *, threshold: int, top_n: int) -> str:
    """
    Daily raw archive digest. Goes to digests/raw/YYYY-MM-DD.md.
    items: scored + merged items, sorted by relevance_score desc, top_n applied.
    """
    lines: list[str] = []
    lines.append(f"# Signal raw: {today}")
    lines.append("")
    lines.append(f"_{len(items)} items, score >= {threshold}, top {top_n}_")
    lines.append("")

    if not items:
        lines.append("> No items met the threshold today.")
        return "\n".join(lines) + "\n"

    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Score | Title | Source | Takeaway |")
    lines.append("|---|-------|-------|--------|----------|")
    for i, item in enumerate(items, 1):
        title = item["title"].replace("|", "\\|")
        source = item["source_name"].replace("|", "\\|")
        score = item["relevance_score"]
        takeaway = (item.get("partner_takeaway") or "").replace("|", "\\|")
        if len(takeaway) > 120:
            takeaway = takeaway[:117] + "..."
        lines.append(f"| {i} | {score} | [{title}]({item['url']}) | {source} | {takeaway} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Items")
    lines.append("")
    for i, item in enumerate(items, 1):
        score = item["relevance_score"]
        tags = _tag_chip(item.get("topic_tags") or [])
        lines.append(f"### {i}. {item['title']}")
        lines.append("")
        meta_bits = [f"**Score:** {score}/10", f"**Source:** {item['source_name']}"]
        if item.get("published"):
            meta_bits.append(f"**Published:** {item['published'][:10]}")
        lines.append(" · ".join(meta_bits))
        lines.append("")
        if tags:
            lines.append(tags)
            lines.append("")
        lines.append(f"**Why this scores {score}/10:** {item.get('score_reason', '').strip()}")
        lines.append("")
        if item.get("partner_takeaway"):
            lines.append(f"**Partner takeaway:** {item['partner_takeaway'].strip()}")
            lines.append("")
        lines.append("**Partner summary**")
        lines.append("")
        lines.append(item.get("partner_summary", "").strip())
        lines.append("")
        lines.append(f"[Read source]({item['url']})")
        lines.append("")
        if item.get("summary"):
            lines.append("<details><summary>Original feed excerpt</summary>")
            lines.append("")
            lines.append(item["summary"])
            lines.append("")
            lines.append("</details>")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_ideas_digest(
    ideas: list[dict],
    *,
    iso_week: str,
    today: str,
    source_items_by_id: dict[str, dict] | None = None,
    stories_by_id: dict[str, dict] | None = None,
) -> str:
    """
    Weekly idea-card digest. Goes to digests/YYYY-WW.md.
    Each idea card maps to a track, optionally references a story and one or
    more source items, and includes a suggested format + image code.
    """
    source_items_by_id = source_items_by_id or {}
    stories_by_id = stories_by_id or {}

    lines: list[str] = []
    lines.append(f"# Signal ideas: week {iso_week}")
    lines.append("")
    lines.append(f"_{len(ideas)} idea cards, generated {today}_")
    lines.append("")

    if not ideas:
        lines.append("> No idea cards generated this week. Check the raw archive or content plan.")
        return "\n".join(lines) + "\n"

    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Track | Title | Format | Image |")
    lines.append("|---|-------|-------|--------|-------|")
    for i, idea in enumerate(ideas, 1):
        title = (idea.get("title") or "").replace("|", "\\|")
        track = idea.get("track", "?")
        fmt = idea.get("format", "?")
        img = idea.get("image_code", "?")
        lines.append(f"| {i} | {track} | {title} | {fmt} | `{img}` |")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Idea cards")
    lines.append("")

    for i, idea in enumerate(ideas, 1):
        track = idea.get("track", "?")
        title = idea.get("title", "(untitled)")
        lines.append(f"### {i}. [{track}] {title}")
        lines.append("")
        lines.append(f"**Hook:** {idea.get('hook', '').strip()}")
        lines.append("")
        lines.append(f"**Format:** `{idea.get('format','?')}`  ·  **Image:** `{idea.get('image_code','?')}`")
        lines.append("")
        if idea.get("partner_takeaway"):
            lines.append(f"**Partner takeaway:** {idea['partner_takeaway'].strip()}")
            lines.append("")
        if idea.get("reasoning"):
            lines.append(f"**Why this post:** {idea['reasoning'].strip()}")
            lines.append("")

        # Resolve story_ref
        story_id = idea.get("story_ref")
        if story_id and story_id in stories_by_id:
            story = stories_by_id[story_id]
            lines.append(f"**Story fuel:** `{story_id}` - {story.get('title','')}")
            lines.append("")
            summary = (story.get("summary") or "").strip()
            if summary:
                lines.append(f"> {summary}")
                lines.append("")

        # Resolve source_refs
        source_refs = idea.get("source_refs") or []
        if source_refs:
            lines.append("**Source fuel:**")
            lines.append("")
            for sid in source_refs:
                item = source_items_by_id.get(sid)
                if item:
                    lines.append(f"- [{item['title']}]({item['url']}) · {item['source_name']} · score {item.get('relevance_score','?')}/10")
                    takeaway = item.get("partner_takeaway")
                    if takeaway:
                        lines.append(f"  - _{takeaway.strip()}_")
                else:
                    lines.append(f"- `{sid}` (item not found in this week's scored set)")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
