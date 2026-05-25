"""
Nine Letters PDF renderer.
Page 1: 3×3 grid + numbered clues.
Page 2: answer key (grid + words listed by length).
"""
import io
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black, Color

from .pdf_utils import (
    PAGE_W, PAGE_H, MARGIN, HEADER_H,
    year_colour, hex_colour,
    draw_header, draw_footer, content_top, content_bottom,
)

CELL = 56      # cell size in points (≈ 20mm)
GRID_W = 3 * CELL
GRID_H = 3 * CELL


def _draw_grid(c, letters: list[str], required: str, colour: str, top_y: float) -> float:
    """Draw the 3×3 letter grid. Returns y of grid bottom."""
    gx = (PAGE_W - GRID_W) / 2
    gy_bottom = top_y - GRID_H

    for idx, letter in enumerate(letters):
        row = idx // 3
        col = idx % 3
        x = gx + col * CELL
        y = top_y - (row + 1) * CELL  # bottom of this cell

        is_req = idx == 4  # centre cell

        # Fill
        c.setFillColor(hex_colour(colour) if is_req else HexColor("#EEF6FB"))
        c.rect(x, y, CELL, CELL, fill=1, stroke=0)

        # Border
        c.setStrokeColor(hex_colour(colour))
        c.setLineWidth(1.5)
        c.rect(x, y, CELL, CELL, fill=0, stroke=1)

        # Letter
        fs = 20
        c.setFont("Helvetica-Bold", fs)
        c.setFillColor(white if is_req else hex_colour(colour))
        lw = c.stringWidth(letter, "Helvetica-Bold", fs)
        c.drawString(x + (CELL - lw) / 2, y + CELL * 0.3, letter)

    return gy_bottom


def _draw_clues(c, words_by_length: dict, colour: str, start_y: float, answers: bool) -> None:
    """Render numbered clues (puzzle) or word lists (answers) in two columns."""
    x_left = MARGIN
    x_right = PAGE_W / 2 + 10
    col_width = PAGE_W / 2 - MARGIN - 10

    y_left = start_y
    y_right = start_y
    clue_num = 1
    use_right = False

    for length in sorted(words_by_length.keys()):
        entries = words_by_length[length]
        label = f"{'★ ' if length == 9 else ''}{length} letter{'s' if length != 1 else ''}"

        x = x_right if use_right else x_left
        y = y_right if use_right else y_left

        # Group heading
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(hex_colour(colour))
        c.drawString(x, y, label)
        y -= 13

        for entry in entries:
            c.setFont("Helvetica", 9)
            c.setFillColor(black)
            if answers:
                text = f"{clue_num}.  {entry['word'].title()}"
            else:
                clue = entry["clue"]
                if len(clue) > 58:
                    clue = clue[:55] + "…"
                text = f"{clue_num}.  {clue}"
            c.drawString(x + 4, y, text)
            y -= 12
            clue_num += 1

        y -= 6  # gap between groups

        if use_right:
            y_right = y
        else:
            y_left = y
        use_right = not use_right


def render_nine_letters_pdf(puzzle: dict, year_group: str = "Y4") -> bytes:
    colour = year_colour(year_group)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    title = f"Nine Letters: {puzzle.get('topic', '').title()}"
    letters = puzzle["letters"]
    required = puzzle["required"]
    words_by_length = puzzle["words_by_length"]

    for page in ("puzzle", "answers"):
        subtitle = "Answers" if page == "answers" else (
            f"Every word must contain the letter  {required}  (highlighted)"
        )
        draw_header(c, title, subtitle, colour)
        draw_footer(c)

        top = content_top()
        grid_bottom = _draw_grid(c, letters, required, colour, top)

        # Instruction below grid
        note_y = grid_bottom - 10
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(
            PAGE_W / 2, note_y,
            f"Your letters:  {'   '.join(letters)}    ★ = {required} required in every word",
        )

        clue_top = note_y - 18
        _draw_clues(c, words_by_length, colour, clue_top, answers=(page == "answers"))
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
