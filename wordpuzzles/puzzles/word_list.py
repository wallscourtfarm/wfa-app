"""
Shared word list loader.
Fetches the English word dictionary from the word-puzzles repo on first use
and caches it in memory for the lifetime of the process.
"""
import urllib.request

_WORDS_URL = (
    "https://raw.githubusercontent.com/wallscourtfarm/word-puzzles/main/assets/words.txt"
)
_word_set: set | None = None


def get_word_set() -> set:
    global _word_set
    if _word_set is None:
        with urllib.request.urlopen(_WORDS_URL, timeout=20) as f:
            _word_set = set(f.read().decode("utf-8").splitlines())
    return _word_set
