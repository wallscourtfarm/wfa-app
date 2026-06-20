"""
Nine Letters puzzle generator.

3×3 grid of letters. Every answer word must contain the centre (required) letter.
Words are grouped by length; each has a clue rather than the word itself.
"""
import json
import random
import re
from collections import Counter

import anthropic

from .word_list import get_word_set


def _letters_fit(word: str, available: Counter) -> bool:
    """Return True if word (lowercase) can be formed from the available letter counts."""
    for letter, count in Counter(word).items():
        if available[letter] < count:
            return False
    return True


def _find_valid_words(nine_word: str, required: str) -> dict[int, list[str]]:
    """
    Find all valid sub-words using only the letters in nine_word,
    where each word contains required and is 4–9 letters long.
    Returns {length: [word, ...], ...}.
    """
    available = Counter(nine_word.lower())
    req = required.lower()
    words = get_word_set()

    by_length: dict[int, list[str]] = {}
    for word in words:
        n = len(word)
        if n < 4 or n > 8:
            continue
        if req not in word:
            continue
        if not _letters_fit(word, available):
            continue
        by_length.setdefault(n, []).append(word)
    return by_length


def _select_words(by_length: dict[int, list[str]], max_per_length: int = 3) -> list[str]:
    """Pick a representative set — up to max_per_length per length, shortest first."""
    selected = []
    for length in sorted(by_length.keys()):
        bucket = by_length[length][:]
        random.shuffle(bucket)
        selected.extend(bucket[:max_per_length])
    return selected


def generate_nine_letters(topic: str, year_group: str, api_key: str) -> dict:
    """
    Generate a Nine Letters puzzle.
    Two API calls:
      1. Get the 9-letter word + required letter.
      2. Get clues for the selected sub-words.
    Returns a dict the PDF renderer and app can consume.
    """
    client = anthropic.Anthropic(api_key=api_key)
    year_num = year_group.replace("Y", "")
    words = get_word_set()

    # ── Call 1: Get the 9-letter word ────────────────────────────────────────
    setup_prompt = f"""Choose a single 9-letter English word related to the topic "{topic}" for a Year {year_num} class (ages {int(year_num)+4}).
If no 9-letter topic word exists, choose any interesting 9-letter English word.

Also choose one letter from that word as the REQUIRED letter — it should be a common letter (not Q, X, Z) that will appear in many sub-words.

Return ONLY valid JSON, no markdown:
{{"nine_letter_word": "SOMETHING", "required_letter": "E", "word_reason": "brief explanation"}}"""

    r1 = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": setup_prompt}],
    )
    raw = re.sub(r"```[a-z]*", "", r1.content[0].text.strip()).strip("`")
    setup = json.loads(raw)

    nine_word = re.sub(r"[^A-Za-z]", "", setup["nine_letter_word"]).upper()
    if len(nine_word) != 9:
        raise ValueError(f"Model returned '{nine_word}' which is not 9 letters.")

    required = setup["required_letter"].upper()[0]
    if required not in nine_word:
        # Fall back: pick the most common letter in the word
        counter = Counter(nine_word)
        required = counter.most_common(1)[0][0]

    # ── Find sub-words from word list ────────────────────────────────────────
    by_length = _find_valid_words(nine_word, required)
    selected = _select_words(by_length, max_per_length=4)

    if len(selected) < 4:
        raise ValueError(
            f"Too few valid sub-words found for '{nine_word}' (required: {required}). "
            "Try a different topic."
        )

    # Always include the 9-letter word itself if it's in the word set (nice bonus)
    # Whether or not it's in the set we'll include it as the target word
    selected_upper = [w.upper() for w in selected]

    # ── Call 2: Get clues for selected words ─────────────────────────────────
    word_list_str = ", ".join(selected_upper)
    clue_prompt = f"""Write a short clue for each of these English words. Clues should be suitable for Year {year_num} primary school pupils (ages {int(year_num)+4}).

Rules:
- Each clue is a brief definition, 4-8 words maximum.
- Do not use the word itself or an obvious root word.
- British English.
- Age-appropriate vocabulary.

Also write a clue for the 9-letter word: {nine_word}

Words to clue: {word_list_str}

Return ONLY valid JSON, no markdown:
{{
  "nine_letter_clue": "clue for {nine_word}",
  "word_clues": [
    {{"word": "WORD1", "clue": "clue here"}},
    ...
  ]
}}"""

    r2 = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": clue_prompt}],
    )
    raw2 = re.sub(r"```[a-z]*", "", r2.content[0].text.strip()).strip("`")
    clue_data = json.loads(raw2)

    # Build words_by_length dict with clues
    clue_map = {entry["word"].upper(): entry["clue"] for entry in clue_data.get("word_clues", [])}

    words_by_length: dict[int, list[dict]] = {}
    for word in selected_upper:
        clue = clue_map.get(word, f"A {len(word)}-letter word")
        words_by_length.setdefault(len(word), []).append({"word": word, "clue": clue})

    # Add the 9-letter word
    words_by_length[9] = [{"word": nine_word, "clue": clue_data.get("nine_letter_clue", "Uses all nine letters")}]

    # Arrange letters: required in position 4 (centre), others shuffled around it
    letter_list = list(nine_word)
    # Remove one instance of required
    for i, ch in enumerate(letter_list):
        if ch == required:
            letter_list.pop(i)
            break
    random.shuffle(letter_list)
    grid_letters = letter_list[:4] + [required] + letter_list[4:]

    return {
        "letters": grid_letters,
        "required": required,
        "nine_letter_word": nine_word,
        "words_by_length": words_by_length,
        "topic": topic,
    }
