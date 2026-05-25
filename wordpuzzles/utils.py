"""
Utilities for word generation.
1. clf_vocabulary — topic-keyword matching against bundled CLF curriculum vocabulary
2. get_words_from_topic — Claude API fallback for topics not in the curriculum database
"""
import json
import os
import re

_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "clf_vocabulary.json")


def _load_vocab():
    with open(_VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_clf_words(topic: str, year_group: str = "Y4") -> tuple[list[str], str]:
    """
    Match topic string against CLF vocabulary keywords.
    Returns (words, matched_topic_label) or ([], "") if no match.
    Only returns words valid for word search: 4-12 letters, no spaces.
    """
    topic_lower = topic.lower().strip()
    data = _load_vocab()
    topics = data.get("topics", {})

    best_key = None
    best_score = 0

    for key, entry in topics.items():
        keywords = entry.get("keywords", [])
        score = 0
        for kw in keywords:
            if kw.lower() in topic_lower or topic_lower in kw.lower():
                score += len(kw)  # longer keyword match scores higher
        if score > best_score:
            best_score = score
            best_key = key

    if not best_key or best_score == 0:
        return [], ""

    entry = topics[best_key]
    raw_words = entry.get("words", [])
    # Filter: no spaces, no hyphens, 4–12 chars
    valid = [
        w for w in raw_words
        if " " not in w and "-" not in w and 4 <= len(w) <= 12
    ]
    label = entry.get("keywords", [best_key])[0].title()
    return valid, label


def get_words_from_topic(
    topic: str,
    year_group: str,
    puzzle_type: str,
    n: int = 16,
    api_key: str = "",
) -> tuple[list[str], str]:
    """
    Build a word list for the given topic:
    1. Pull any matching CLF curriculum vocabulary.
    2. Ask Claude for topic-specific words to fill the remainder.
    Returns (words, display_title).
    """
    clf_words, clf_label = get_clf_words(topic, year_group)

    # If we have enough CLF words we still ask Claude to complement,
    # because CLF vocab is curriculum metalanguage — we want subject nouns too.
    target = max(n, 12)
    clf_sample = clf_words[:8]  # take up to 8 from the curriculum list

    if not api_key:
        # No Claude — return CLF words only if we have them
        if clf_words:
            display = clf_label or topic
            return [w.upper() for w in clf_words[:target]], display
        return [], topic

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    year_num = year_group.replace("Y", "")

    clf_hint = ""
    if clf_sample:
        clf_hint = (
            f"\nThe following words come from the CLF Y{year_num} curriculum vocabulary for this topic — "
            f"INCLUDE ALL OF THEM in your list: {', '.join(clf_sample)}."
        )

    prompt = f"""Generate {target} vocabulary words for a Year {year_num} primary school class on the topic of "{topic}".
These words will be used in a {puzzle_type} puzzle.{clf_hint}

Rules:
- Each word must be a single word (no spaces, no hyphens).
- Between 4 and 12 letters long.
- Appropriate for age {int(year_num) + 4} (Year {year_num}).
- Directly relevant to the topic.
- Mix of shorter (4–6 letters) and longer (7–12 letters) words.
- British English spelling.
- Include subject-specific nouns, verbs and adjectives — not just metalanguage.

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{"words": ["word1", "word2", ...], "display_title": "Short human-readable topic name"}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"```[a-z]*", "", raw).strip().strip("`")
    data = json.loads(raw)

    returned = [w.strip().upper() for w in data.get("words", []) if w.strip()]
    display  = data.get("display_title", topic)

    # Deduplicate, preserving order; CLF words first where they appear
    seen = set()
    final = []
    for w in returned:
        if w not in seen:
            seen.add(w)
            final.append(w)

    return final, display
