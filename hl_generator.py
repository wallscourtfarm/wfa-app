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

_STANDARD_SYSTEM = ("""You are an expert Year 4 primary teacher in England producing weekly home learning.

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

"""
+ """

MATHS NOTES (if provided by teacher): Free-form instructions about how to structure or lay out specific questions.
Follow these exactly as written — they override any default assumptions above.
The word "grid" in maths notes refers to the column method Th H T O grid boxes, NOT the coordinate grid.

"""
+ _GRID_SCHEMA
+ _GRID_RULES
+ """

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
    {"heading": "...", "text": "...", "answer_type": "lines", "answer_lines": 0},
    {"heading": "...", "text": "...", "answer_lines": 0},
    {"heading": "...", "text": "...", "answer_lines": 0},
    {"heading": "...", "text": "...", "answer_lines": 2},
    {"heading": "Problem solving", "text": "...", "answer_lines": 2}
  ],
  "passage": "...",
  "reading_questions": [
    {"type": "retrieval",  "text": "...", "lines": 2},
    {"type": "retrieval",  "text": "...", "lines": 2},
    {"type": "vocabulary", "text": "...", "lines": 2},
    {"type": "inference",  "text": "...", "lines": 3}
  ]
}


══ WORKED EXAMPLES — follow these patterns exactly ══

EXAMPLE A — Geometry / Symmetry topic (uses grid):
{
  "maths_instruction": "Use the grid to answer questions 1, 2 and 3. Answer questions 4 and 5 in the space below.",
  "grid_size": 10,
  "grid_elements": [
    {"type":"polygon","vertices":[[2,7],[4,9],[6,7],[4,5]],"fill":"lightblue","color":"#1A3C6E"},
    {"type":"mirror_v","x":8,"color":"#cc0000"}
  ],
  "questions": [
    {"heading":"Q1","text":"Reflect the blue diamond shape across the red mirror line. Draw the reflection on the grid.","answer_type":"lines","answer_lines":0},
    {"heading":"Q2","text":"Draw a horizontal line of symmetry through the point (3, 5). Mark two shapes that are symmetrical about it.","answer_type":"lines","answer_lines":0},
    {"heading":"Q3","text":"Plot these points and join them to make a rectangle: (1,1), (1,4), (5,4), (5,1). How many lines of symmetry does it have?","answer_type":"lines","answer_lines":0},
    {"heading":"Q4","text":"An isosceles triangle has exactly one line of symmetry. It passes through one vertex and the midpoint of the opposite side. Describe where this line goes on a triangle with vertices at (0,0), (4,0) and (2,4).","answer_type":"lines","answer_lines":2},
    {"heading":"Problem solving","text":"Mia says this shape has 4 lines of symmetry. The shape is a rectangle that is not a square. Is Mia correct? Explain your answer.","answer_type":"lines","answer_lines":2}
  ],
  "passage": "...",
  "reading_questions": [...]
}

EXAMPLE B — Column addition and subtraction (NO grid, column method grids in PDF):
{
  "maths_instruction": "Use the column method grids to show your working.",
  "grid_size": 0,
  "grid_elements": [],
  "questions": [
    {"heading":"Q1","text":"Work out each calculation using the column method.\na) 4,526 + 3,847\nb) 5,634 + 728","answer_type":"column_method","answer_lines":0},
    {"heading":"Q2","text":"Work out each subtraction using the column method.\na) 7,293 − 4,658\nb) 6,841 − 947","answer_type":"column_method","answer_lines":0},
    {"heading":"Q3","text":"Work out each calculation. Be careful — one is addition and one is subtraction.\na) 3,479 + 2,865\nb) 9,142 − 386","answer_type":"column_method","answer_lines":0},
    {"heading":"Q4","text":"A cinema sold 3,847 tickets on Friday and 2,569 tickets on Saturday. How many tickets were sold in total over the two days? Show your working using the column method.","answer_type":"lines","answer_lines":3},
    {"heading":"Problem solving","text":"Maya says that 4,672 + 395 = 5,167. Is Maya correct? Use the column method to check and explain your answer.","answer_type":"lines","answer_lines":2}
  ],
  "passage": "...",
  "reading_questions": [...]
}

EXAMPLE C — Times tables / number (NO grid):
{
  "maths_instruction": "Answer all questions in the space below each one.",
  "grid_size": 0,
  "grid_elements": [],
  "questions": [
    {"heading":"Q1","text":"Complete these multiplication facts.\na) 7 × 8 = ___   b) 9 × 6 = ___   c) 12 × 7 = ___   d) 8 × 11 = ___","answer_type":"lines","answer_lines":1},
    {"heading":"Q2","text":"Use a multiplication fact to work out each division.\na) 56 ÷ 7 = ___   b) 54 ÷ 9 = ___   c) 84 ÷ 12 = ___","answer_type":"lines","answer_lines":1},
    {"heading":"Q3","text":"Fill in the missing numbers.\na) 7 × ___ = 63   b) ___ × 8 = 96   c) 11 × ___ = 132","answer_type":"lines","answer_lines":1},
    {"heading":"Q4","text":"A baker puts 9 buns on each tray. She uses 7 trays. How many buns does she bake altogether? Write the multiplication sentence and the answer.","answer_type":"lines","answer_lines":2},
    {"heading":"Problem solving","text":"Theo says: 'If I know 6 × 8 = 48, I can work out 60 × 8 and 6 × 80.' Is Theo correct? Write both answers and explain the pattern.","answer_type":"lines","answer_lines":2}
  ],
  "passage": "...",
  "reading_questions": [...]
}

KEY RULES derived from these examples:
- Column method topics: ALWAYS answer_type "column_method" for Q1-Q3, ALWAYS grid_size 0, ALWAYS grid_elements [].
- Grid topics: Q1-Q3 use the grid (answer_lines 0), Q4+Q5 do NOT use the grid (answer_lines 2).
- No-grid topics: ALL five questions use answer_type "lines" with appropriate answer_lines.
- Q4 is always a word problem or standalone skill with answer_lines 2 or 3.
- Q5 is always a misconception challenge naming a fictional child (never a real name).
- Headings for Q1-Q4: "Q1", "Q2", "Q3", "Q4". Heading for Q5: "Problem solving".
- Never use "trickier", "easier", "harder". For 2D shapes, use "side" not "edge".
""")

_ADAPTED_SYSTEM = ("""You are an expert Year 4 primary teacher producing ADAPTED home learning for children at Year 1/2 level.

══ MATHS (left half) ══
Grid: 6×6, 2-3 simple elements only. Omit if topic needs no grid (grid_elements:[], grid_size:0).
4 heavily scaffolded questions:
  Q1 — circle the correct answer: show 3 options as "Circle:  A   B   C" in the question text. answer_lines:0
  Q2 — fill in the blank: short sentence frame with blanks. answer_lines:0
  Q3 — complete the sentence: provide a sentence starter. answer_lines:1
  Q4 — true or false: one statement, "Circle:  TRUE     FALSE" in the question text. answer_lines:0
Simple vocabulary. Short sentences. No multi-step reasoning.

"""
+ """

MATHS NOTES (if provided by teacher): Free-form instructions about how to structure or lay out specific questions.
Follow these exactly as written — they override any default assumptions above.
The word "grid" in maths notes refers to the column method Th H T O grid boxes, NOT the coordinate grid.

"""
+ _GRID_SCHEMA
+ _GRID_RULES
+ """
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
    {"heading": "...", "text": "... Circle:  A   B   C", "answer_lines": 0},
    {"heading": "...", "text": "...___ ...", "answer_lines": 0},
    {"heading": "...", "text": "Complete the sentence: ...", "answer_lines": 1},
    {"heading": "True or false?", "text": "... Circle:  TRUE     FALSE", "answer_lines": 0}
  ],
  "passage": "...",
  "reading_questions": [
    {"type": "retrieval",  "text": "...", "lines": 2},
    {"type": "retrieval",  "text": "...", "lines": 2},
    {"type": "vocabulary", "text": "...", "lines": 1},
    {"type": "inference",  "text": "...", "lines": 2}
  ]
}
""")


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


_COLUMN_TOPIC_KEYWORDS = {
    "column method", "written method", "written addition",
    "written subtraction", "formal written"
}

def _topic_needs_column(maths_topic):
    t = maths_topic.lower()
    return any(kw in t for kw in _COLUMN_TOPIC_KEYWORDS)


def _validate(data, version, maths_topic=""):
    for k in ("maths_instruction", "grid_elements", "questions", "passage", "reading_questions"):
        if k not in data:
            raise ValueError(f"Missing key: '{k}'")

    n_q = 5 if version == "standard" else 4
    if len(data["questions"]) != n_q:
        raise ValueError(f"Expected {n_q} maths questions, got {len(data['questions'])}")

    for i, q in enumerate(data["questions"]):
        if not q.get("heading") or not q.get("text"):
            raise ValueError(f"Maths Q{i+1} missing heading or text")

    # Column method validation
    if _topic_needs_column(maths_topic) and version == "standard":
        errors = []
        for i in range(min(3, n_q)):
            atype = data["questions"][i].get("answer_type", "lines")
            if atype != "column_method":
                errors.append(f"Q{i+1} must have answer_type 'column_method' for a column method topic, got '{atype}'")
        if errors:
            raise ValueError(
                "Column method topic requires answer_type='column_method' for Q1-Q3. "
                + " ".join(errors)
                + " Refer to EXAMPLE B in the worked examples."
            )

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
        _validate(data, version, maths_topic)
    except ValueError as e:
        err_str = str(e)
        retry_user = (
            user + "\n\nPREVIOUS ATTEMPT FAILED VALIDATION:\n" + err_str +
            "\n\nPlease fix the issue and regenerate. Refer to the worked examples in the system prompt."
        )
        data = _call(system, retry_user)
        _validate(data, version, maths_topic)
    return data

