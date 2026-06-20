"""
Word Ladder puzzle generator.
BFS finds shortest path between two words, changing one letter per step.
"""
import json
import re
from collections import deque

import anthropic

from .word_list import get_word_set


def bfs_ladder(start: str, end: str, word_set: set) -> list[str] | None:
    """
    BFS from start to end (both lowercase, same length).
    Returns full path including start and end, or None if no path.
    Caps at 150 000 visited nodes to avoid runaway searches.
    """
    length = len(start)
    if len(end) != length:
        return None

    same_len = {w for w in word_set if len(w) == length}
    if start not in same_len or end not in same_len:
        return None

    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    visited: set[str] = {start}

    while queue and len(visited) < 150_000:
        word, path = queue.popleft()
        for i in range(length):
            for ch in "abcdefghijklmnopqrstuvwxyz":
                if ch == word[i]:
                    continue
                neighbour = word[:i] + ch + word[i + 1:]
                if neighbour == end:
                    return path + [end]
                if neighbour in same_len and neighbour not in visited:
                    visited.add(neighbour)
                    queue.append((neighbour, path + [neighbour]))
    return None


def _get_hint_clue(word: str, year_num: str, client) -> str:
    """Ask Claude for a short definition clue for the hint word."""
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=80,
        messages=[{
            "role": "user",
            "content": (
                f"Write a very short clue (4-6 words) for the English word '{word}'. "
                f"It should make sense to a Year {year_num} pupil (age {int(year_num)+4}). "
                f"Just the clue itself — no full stops, no quotes, no extra explanation."
            ),
        }],
    )
    return resp.content[0].text.strip().strip(".")


def generate_word_ladder(topic: str, year_group: str, difficulty: str, api_key: str) -> dict:
    """
    Generate a Word Ladder puzzle.

    difficulty affects word length preference and minimum path length:
      Easy   -> 4-letter words, at least 3 intermediate steps
      Medium -> 5-letter words, at least 5 intermediate steps
      Hard   -> 5-letter words, at least 7 intermediate steps

    Returns dict: start, end, path, word_length, num_steps, hint_idx, hint_word, hint_clue, topic.
    """
    client = anthropic.Anthropic(api_key=api_key)
    year_num = year_group.replace("Y", "")
    word_set = get_word_set()

    # 5-letter words naturally give longer BFS paths
    preferred_length = "4" if difficulty == "Easy" else "5"
    min_steps = {"Easy": 3, "Medium": 5, "Hard": 7}.get(difficulty, 4)
    max_steps = {"Easy": 6, "Medium": 9, "Hard": 14}.get(difficulty, 9)
    step_hint = {"Easy": "3-5", "Medium": "5-8", "Hard": "8-12"}.get(difficulty, "5-8")

    prompt = f"""Suggest word pairs for a Word Ladder puzzle for Year {year_num} pupils (topic: "{topic}").

Rules:
- Each word must be exactly {preferred_length} letters long.
- Both words in a pair must be common English words a Year {year_num} pupil would recognise.
- The two words should be very DIFFERENT in sound and spelling to create a long path. Avoid pairs that share many letters.
- We need approximately {step_hint} intermediate steps, so choose words that are genuinely far apart.
- Ideally at least one word relates to "{topic}", but path length matters more than topic.
- Provide 8 different pairs as fallbacks.

Return ONLY valid JSON, no markdown:
{{"pairs": [{{"start": "chair", "end": "table"}}, ...]}}"""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = re.sub(r"```[a-z]*", "", resp.content[0].text.strip()).strip("`")
    data = json.loads(raw)

    best_path = None
    best_start = None
    best_end = None
    best_steps = 0

    for pair in data.get("pairs", []):
        start = pair["start"].lower().strip()
        end = pair["end"].lower().strip()
        if start == end or len(start) != len(end):
            continue
        path = bfs_ladder(start, end, word_set)
        if path is None:
            continue
        steps = len(path) - 2
        if min_steps <= steps <= max_steps:
            if best_path is None or steps > best_steps:
                best_path = path
                best_start = start
                best_end = end
                best_steps = steps
        elif best_path is None and steps >= 2:
            best_path = path
            best_start = start
            best_end = end
            best_steps = steps

    if best_path is None:
        raise ValueError(
            "Could not find a valid word ladder path. Try a different topic or difficulty."
        )

    path = best_path
    mid_idx = len(path) // 2
    mid_idx = max(1, min(mid_idx, len(path) - 2))
    hint_word = path[mid_idx]
    hint_clue = _get_hint_clue(hint_word, year_num, client)

    return {
        "start": best_start.upper(),
        "end": best_end.upper(),
        "path": [w.upper() for w in path],
        "word_length": len(best_start),
        "num_steps": len(path) - 2,
        "hint_idx": mid_idx,
        "hint_word": hint_word.upper(),
        "hint_clue": hint_clue,
        "topic": topic,
    }
