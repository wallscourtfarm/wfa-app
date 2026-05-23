"""
hl_generator.py
Generates weekly home learning content via the Anthropic API.
"""

import anthropic
import json
import re

client = anthropic.Anthropic()

_GRID_SCHEMA = """
Grid element types (JSON objects in grid_elements array):
  point:     {"type":"point",     "x":N,"y":N,"label":"A","color":"#1A3C6E"}
  arrow:     {"type":"arrow",     "x1":N,"y1":N,"x2":N,"y2":N,"label":"P→Q","color":"#1A3C6E"}
  triangle:  {"type":"triangle",  "vertices":[[x,y],[x,y],[x,y]],"fill":"lightblue","color":"#1A3C6E"}
  rectangle: {"type":"rectangle", "x1":N,"y1":N,"x2":N,"y2":N,"fill":"none","color":"#1A3C6E",
               "vertex_labels":[{"x":N,"y":N,"label":"A"},{"x":N,"y":N,"label":"B"},
                                 {"x":N,"y":N,"label":"C"},{"x":N,"y":N,"label":"D"}]}
  star:      {"type":"star",      "x":N,"y":N,"label":"S","color":"#1A3C6E"}
  polygon:   {"type":"polygon",   "vertices":[[x,y],...],"fill":"none","color":"#1A3C6E"}
  mirror_v:  {"type":"mirror_v",  "x":N,"color":"#cc0000"}
  mirror_h:  {"type":"mirror_h",  "y":N,"color":"#cc0000"}

All coordinates must be integers within the grid. Default colour "#1A3C6E". Mirror lines "#cc0000".
"""

_GRID_RULES = """
GRID LAYOUT RULES — critical:
1. Each question that uses the grid should have its own clearly separate area. Never overlap elements
   from different questions. Place Q1 elements in one region of the grid, Q2 elements in a different
   region with clear space between them.
2. If a question asks the child to DRAW something (reflect a shape, draw a line of symmetry, draw a
   hexagon), the answer space must be EMPTY on the grid — do not pre-draw the answer. Only draw the
   starting shape the child works from.
3. Maximum 3-4 distinct elements on any grid. Keep it uncluttered.
4. For symmetry tasks: one clear shape (triangle, rectangle, or simple polygon) with one mirror line.
   Do NOT put multiple different shapes on the grid at once.
5. For translation: one clearly labelled starting shape/point and a clear endpoint or arrow.
6. For coordinates: labelled points or a simple polygon — not both together.

REFLECTION DISTANCE RULE — this is critical and commonly wrong:
For any shape that must be reflected across a mirror line, BOTH the shape AND its reflection must
fit within the grid (0 to grid_size inclusive). This means:
- mirror_h at y=M on a 10×10 grid: all shape y-coordinates must be within 1 unit EITHER side of M,
  and at most min(M, grid_size−M) units away from M.
  Example: mirror_h y=1 → shape y-coords must stay in [0, 2] — no point further than 1 from the line.
  Example: mirror_h y=5 → shape y-coords can be in [0, 10] but reflection must also stay in [0, 10].
- mirror_v at x=M: same rule horizontally.
ALWAYS CHECK: if a shape point is at distance D from the mirror, the reflection lands at distance D
on the other side. If that puts it outside [0, grid_size], move the mirror OR move the shape.
The safest approach for a 10×10 grid: place the mirror near the centre (x=5 or y=5) so both sides
have room. Only place the mirror near an edge (y=1, y=2) if the shape is very close to that line.

GRID TOPIC GUIDANCE:
  Translation / directions → points (A, B), single arrow (P→Q), one triangle or star — 10×10 grid
  Coordinates              → labelled points or one polygon/rectangle — 10×10 grid
  Symmetry / reflection    → ONE simple shape + one mirror line per question — 10×10 grid
  Perimeter / area         → one rectangle with vertex_labels only — 10×10 grid
  Times tables / mental    → no grid: grid_elements:[], grid_size:0
  Fractions / number line  → no grid: grid_elements:[], grid_size:0
"""

_STANDARD_SYSTEM = f"""You are an expert Year 4 primary teacher in England producing weekly home learning.

The home learning consolidates what was taught that week. It has two halves on A4 landscape.

══ MATHS (left half) ══
Grid: 10×10 coordinate grid. Omit entirely if topic needs no grid (set grid_elements:[], grid_size:0).
Instruction: one italic line saying which questions use the grid.
5 questions with numbered bold headings:
  Q1, Q2, Q3 — use the grid (answer_lines:0 — children draw or mark on the grid)
  Q4          — standalone second skill, no grid, answer_lines:2
  Q5          — misconception challenge: name a fictional child making a wrong claim,
                ask "Is [name] correct? Explain your answer." answer_lines:2

Question rules:
  Never use "trickier", "easier", "harder". For 2D shapes: "side" not "edge".
  Write clear, direct questions for age 8-9. Each question must be unambiguous.

Column addition/subtraction topics (e.g. "column method", "written addition", "written subtraction"):
  - Set grid_elements:[], grid_size:0 (no coordinate grid needed).
  - Set maths_instruction to: "Use the column method grids to show your working."
  - Q1, Q2, Q3: each question has TWO calculations (label a and b in the question text).
    Use a MIX of digit lengths: some 4-digit + 4-digit, some 4-digit + 3-digit (e.g. 3627 + 492).
    Set answer_type:"column_method", answer_lines:0. The PDF will draw Th H T O grid boxes automatically.
  - Q4: a word problem requiring column method. answer_type:"lines", answer_lines:3.
  - Q5: misconception challenge. answer_type:"lines", answer_lines:2.

{_GRID_SCHEMA}
{_GRID_RULES}

══ READING (right half) ══
Passage: 170-190 words. Original narrative prose — do NOT copy the actual book text.
Write a new scene or continuation in the book's style and characters.
Single flowing paragraph, no line breaks within the passage.
If a specific vocabulary word is provided, plant it naturally in the passage so it becomes
the clear and unambiguous answer for the find-and-copy question.

4 questions in this exact order:
  Q1 retrieval  — factual, directly stated. lines:2
  Q2 retrieval  — factual, directly stated. lines:2
  Q3 vocabulary — "Find and copy a word that means [definition]." Exactly one clear answer. lines:2
  Q4 inference  — "What do you think [X]? Use clues from the text to explain your answer." lines:3

OUTPUT: Valid JSON only. No preamble. No markdown fences.

{{
  "maths_instruction": "Use the grid to answer questions 1, 2 and 3. For questions 4 and 5, use the space below.",
  "grid_elements": [...],
  "grid_size": 10,
  "questions": [
    {{"heading": "...", "text": "...", "answer_type": "lines", "answer_lines": 0}},
    {{"heading": "...", "text": "...", "answer_lines": 0}},
    {{"heading": "...", "text": "...", "answer_lines": 0}},
    {{"heading": "...", "text": "...", "answer_lines": 2}},
    {{"heading": "Problem solving", "text": "...", "answer_lines": 2}}
  ],
  "passage": "...",
  "reading_questions": [
    {{"type": "retrieval",  "text": "...", "lines": 2}},
    {{"type": "retrieval",  "text": "...", "lines": 2}},
    {{"type": "vocabulary", "text": "...", "lines": 2}},
    {{"type": "inference",  "text": "...", "lines": 3}}
  ]
}}
"""

_ADAPTED_SYSTEM = f"""You are an expert Year 4 primary teacher producing ADAPTED home learning for children at Year 1/2 level.

══ MATHS (left half) ══
Grid: 6×6, 2-3 simple elements only. Omit if topic needs no grid (grid_elements:[], grid_size:0).
4 heavily scaffolded questions:
  Q1 — circle the correct answer: show 3 options as "Circle:  A   B   C" in the question text. answer_lines:0
  Q2 — fill in the blank: short sentence frame with blanks. answer_lines:0
  Q3 — complete the sentence: provide a sentence starter. answer_lines:1
  Q4 — true or false: one statement, "Circle:  TRUE     FALSE" in the question text. answer_lines:0
Simple vocabulary. Short sentences. No multi-step reasoning.

{_GRID_SCHEMA}
{_GRID_RULES}
For adapted: grid_size:6. At most 3 simple elements, well-separated.

══ READING (right half) ══
Passage: 110-130 words. Short sentences (8-12 words). High-frequency everyday words only.
No Latinate or multi-syllable words in the passage body. Original — do NOT copy the book.
If a specific vocabulary word is provided and it is accessible at Y1/2 level, use a simpler
synonym version; otherwise choose your own findable word.

4 questions in this exact order:
  Q1 retrieval  — simple factual. lines:2
  Q2 retrieval  — simple factual. lines:2
  Q3 vocabulary — "Find and copy a word that means [very simple definition]." Unambiguous. lines:1
  Q4 inference  — "Why do you think [X]?" Short scaffold. lines:2

OUTPUT: Valid JSON only. No preamble. No markdown fences.

{{
  "maths_instruction": "Use the grid to answer the questions below.",
  "grid_elements": [...],
  "grid_size": 6,
  "questions": [
    {{"heading": "...", "text": "... Circle:  A   B   C", "answer_lines": 0}},
    {{"heading": "...", "text": "...___ ...", "answer_lines": 0}},
    {{"heading": "...", "text": "Complete the sentence: ...", "answer_lines": 1}},
    {{"heading": "True or false?", "text": "... Circle:  TRUE     FALSE", "answer_lines": 0}}
  ],
  "passage": "...",
  "reading_questions": [
    {{"type": "retrieval",  "text": "...", "lines": 2}},
    {{"type": "retrieval",  "text": "...", "lines": 2}},
    {{"type": "vocabulary", "text": "...", "lines": 1}},
    {{"type": "inference",  "text": "...", "lines": 2}}
  ]
}}
"""


def _call(system, user, max_tokens=3500):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*',     '', raw)
    raw = re.sub(r'```\s*$',     '', raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw:\n{raw[:500]}")


def _get_all_points(element):
    """Return all coordinate points from a grid element."""
    t = element.get("type", "")
    if t in ("triangle", "polygon"):
        return element.get("vertices", [])
    if t == "rectangle":
        x1, y1 = element.get("x1", 0), element.get("y1", 0)
        x2, y2 = element.get("x2", 0), element.get("y2", 0)
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if t in ("point", "star"):
        return [[element.get("x", 0), element.get("y", 0)]]
    if t in ("arrow",):
        return [[element.get("x1", 0), element.get("y1", 0)],
                [element.get("x2", 0), element.get("y2", 0)]]
    return []


def _validate_grid_geometry(elements, grid_size):
    """Check that any shapes to be reflected actually fit within the grid when reflected."""
    mirrors_h = [e["y"] for e in elements if e.get("type") == "mirror_h"]
    mirrors_v = [e["x"] for e in elements if e.get("type") == "mirror_v"]
    shapes    = [e for e in elements if e.get("type") not in ("mirror_h", "mirror_v",
                                                               "point", "star", "arrow")]
    if not shapes:
        return  # nothing to reflect

    errors = []
    for shape in shapes:
        pts = _get_all_points(shape)
        if not pts:
            continue
        for my in mirrors_h:
            for (x, y) in pts:
                ref_y = 2 * my - y
                if not (0 <= ref_y <= grid_size):
                    errors.append(
                        f"Shape point ({x},{y}) reflects across mirror_h y={my} "
                        f"to y={ref_y:.1f}, which is outside the grid (0–{grid_size}). "
                        f"Move the mirror or the shape so the reflection fits."
                    )
        for mx in mirrors_v:
            for (x, y) in pts:
                ref_x = 2 * mx - x
                if not (0 <= ref_x <= grid_size):
                    errors.append(
                        f"Shape point ({x},{y}) reflects across mirror_v x={mx} "
                        f"to x={ref_x:.1f}, which is outside the grid (0–{grid_size}). "
                        f"Move the mirror or the shape so the reflection fits."
                    )
    if errors:
        raise ValueError("Grid reflection geometry error:\n" + "\n".join(errors))


def _validate(data, version):
    for k in ("maths_instruction", "grid_elements", "questions", "passage", "reading_questions"):
        if k not in data:
            raise ValueError(f"Missing key: '{k}'")
    n_q = 5 if version == "standard" else 4
    if len(data["questions"]) != n_q:
        raise ValueError(f"Expected {n_q} maths questions, got {len(data['questions'])}")
    for i, q in enumerate(data["questions"]):
        if not q.get("heading") or not q.get("text"):
            raise ValueError(f"Maths Q{i+1} missing heading or text")
    if len(data["reading_questions"]) != 4:
        raise ValueError(f"Expected 4 reading questions, got {len(data['reading_questions'])}")
    expected = ["retrieval", "retrieval", "vocabulary", "inference"]
    for i, (rq, et) in enumerate(zip(data["reading_questions"], expected)):
        if rq.get("type") != et:
            raise ValueError(f"Reading Q{i+1}: expected '{et}', got '{rq.get('type')}'")
    wc = len(data["passage"].split())
    if version == "standard" and not (140 <= wc <= 220):
        raise ValueError(f"Passage word count {wc} — expected ~170-190 words")
    if version == "adapted" and not (90 <= wc <= 150):
        raise ValueError(f"Adapted passage word count {wc} — expected ~110-130 words")
    # Grid geometry
    gs = data.get("grid_size") or 10
    _validate_grid_geometry(data.get("grid_elements", []), gs)


def generate_hl_content(
    maths_topic, reading_topic, week_ref,
    version="standard",
    maths_notes="",
    vocab_word="",
):
    """
    Generate complete HL content for one version.

    maths_topic   e.g. "Symmetry of polygons"
    reading_topic e.g. "Buddhism — the story of Siddhartha"
    week_ref      e.g. "T5W5"
    version       "standard" | "adapted"
    maths_notes   optional — e.g. "Q1: triangle beside mirror line. Q3: blank drawing space."
    vocab_word    optional — e.g. "enlightened"
    """
    system = _STANDARD_SYSTEM if version == "standard" else _ADAPTED_SYSTEM

    notes_line = f"\nMATHS NOTES: {maths_notes}" if maths_notes else ""
    vocab_line = f"\nKEY VOCABULARY WORD TO PLANT IN PASSAGE: {vocab_word}" if vocab_word else ""

    user = (
        f"WEEK: {week_ref}\n"
        f"MATHS TOPIC: {maths_topic}{notes_line}\n"
        f"READING TEXT / FOCUS: {reading_topic}{vocab_line}\n\n"
        "Generate the complete home learning content now."
    )

    data = _call(system, user)
    try:
        _validate(data, version)
    except ValueError as e:
        err_str = str(e)
        if "Grid reflection geometry" in err_str:
            # Retry once with the error fed back
            retry_user = (
                user + "\n\nPREVIOUS ATTEMPT FAILED GEOMETRY CHECK:\n" + err_str +
                "\n\nFix the grid elements so all reflections fit within the grid and try again."
            )
            data = _call(system, retry_user)
            _validate(data, version)
        else:
            raise
    return data

