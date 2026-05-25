"""
Word Scramble puzzle generator.
Shuffles each word's letters; guarantees the scrambled form differs from the original.
"""
import random


def _scramble(word: str) -> str:
    """Shuffle letters until the result differs from the original (or we run out of attempts)."""
    letters = list(word)
    for _ in range(30):
        random.shuffle(letters)
        if "".join(letters) != word:
            return "".join(letters)
    # Fallback: swap first two letters if possible
    if len(letters) >= 2:
        letters[0], letters[1] = letters[1], letters[0]
    return "".join(letters)


def generate_word_scramble(words: list[str], difficulty: str = "Medium") -> list[dict]:
    """
    Returns list of dicts: {original, scrambled, blank_hint}

    difficulty controls word-length preference:
      Easy   → 4–6 letters, first letter revealed in hint
      Medium → 5–8 letters, blank line hint (length only)
      Hard   → 7–12 letters, blank line hint (length only)
    """
    upper_words = [w.upper().strip() for w in words if w.strip()]

    if difficulty == "Easy":
        preferred = [w for w in upper_words if 4 <= len(w) <= 6]
        pool = preferred if len(preferred) >= 5 else upper_words
        reveal_first = True
    elif difficulty == "Hard":
        preferred = [w for w in upper_words if len(w) >= 7]
        pool = preferred if len(preferred) >= 5 else upper_words
        reveal_first = False
    else:  # Medium
        preferred = [w for w in upper_words if 5 <= len(w) <= 8]
        pool = preferred if len(preferred) >= 5 else upper_words
        reveal_first = False

    # Deduplicate, preserve order, cap at 15
    seen: set[str] = set()
    final: list[str] = []
    for w in pool:
        if w not in seen and len(w) >= 3:
            seen.add(w)
            final.append(w)
        if len(final) == 15:
            break

    result = []
    for word in final:
        scrambled = _scramble(word)
        if reveal_first:
            blank_hint = word[0] + " _" * (len(word) - 1)
        else:
            blank_hint = "_ " * len(word)
        result.append({
            "original": word,
            "scrambled": scrambled,
            "blank_hint": blank_hint.strip(),
        })
    return result
