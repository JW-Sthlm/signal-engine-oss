Date: {today}
Lookback: last {lookback_days} days

Here are {n_items} candidates pulled from RSS and podcast feeds. Score each item against the criteria in the system message.

For each item, return: id, relevance_score (1-10), score_reason (one sentence), topic_tags (1-3 short tags from the editorial scope), partner_takeaway (one sentence: what the reader takes away, or empty string if there isn't one), partner_summary (3 sentences per the template), promo_only (true/false per the definition in the system message).

Items:
{items_json}

Return ONLY a JSON array. Preserve the id field exactly as received. Return all items in the input.
