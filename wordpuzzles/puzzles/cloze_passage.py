"""
Cloze Passage puzzle generator.
Asks Claude for a short passage with blanks, using ___N___ markers.
"""
import json
import random
import re

import anthropic


def generate_cloze(topic: str, year_group: str, difficulty: str, api_key: str) -> dict:
    """
    Generate a cloze (fill-in-the-blank) passage.

    Returns dict:
      passage_full        — complete passage
      passage_with_blanks — passage with ___1___, ___2___ etc. in place of gap words
      blanks              — list of gap words in order
      word_bank           — shuffled copy of blanks (empty list if Hard)
      show_bank           — bool
      topic               — topic string
    """
    client = anthropic.Anthropic(api_key=api_key)
    year_num = year_group.replace("Y", "")
    age = int(year_num) + 4
    show_bank = difficulty != "Hard"
    num_gaps = {"Easy": 8, "Medium": 10, "Hard": 12}.get(difficulty, 10)

    prompt = f"""Write a short informative passage about "{topic}" suitable for Year {year_num} primary school pupils (age {age}).

Requirements:
- 5–7 sentences, around 100–130 words.
- Simple, clear language appropriate for age {age}.
- British English spelling.
- Factually accurate and curriculum-appropriate.

Then select exactly {num_gaps} words to remove as blanks. Choose only content words (nouns, verbs, adjectives) that are clearly connected to the topic — not articles, conjunctions or prepositions.

Number the gaps ___1___, ___2___, etc. in order of appearance.

Return ONLY valid JSON, no markdown:
{{
  "passage_full": "The full passage text here.",
  "blanks": ["word1", "word2", ...],
  "passage_with_blanks": "The passage with ___1___, ___2___ etc. replacing the chosen words."
}}

Make sure passage_with_blanks has exactly {num_gaps} numbered markers in order."""

    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = re.sub(r"```[a-z]*", "", resp.content[0].text.strip()).strip("`")
    data = json.loads(raw)

    blanks: list[str] = data["blanks"]
    word_bank = blanks[:] if show_bank else []
    if show_bank:
        random.shuffle(word_bank)

    return {
        "passage_full": data["passage_full"],
        "passage_with_blanks": data["passage_with_blanks"],
        "blanks": blanks,
        "word_bank": word_bank,
        "show_bank": show_bank,
        "topic": topic,
    }
