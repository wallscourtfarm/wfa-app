"""
Word Ladder PDF renderer.
Page 1: ladder with start/end filled, intermediate rungs blank, one hint clue shown.
Page 2: complete solved ladder.
"""
import io
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black

from .pdf_utils import (
    PAGE_W, PAGE_H, MARGIN, HEADER_H,
    year_colour, hex_colour,
    draw_header, draw_footer, content_top,
)

BOX_W = 140
BOX_H = 32
GAP = 10
STILE_OFFSET = 18   # horizontal distance from box edge to stile line


def _draw_ladder(c, path: list[str], colour: str, top_y: float, show_answers: bool,
                 hint_idx: int = None, hint_clue: str = None) -> None:
    n = len(path)
    bx = (PAGE_W - BOX_W) / 2
    stile_left = bx - STILE_OFFSET
    stile_right = bx + BOX_W + STILE_OFFSET

    for i, word in enumerate(path):
        is_first = i == 0
        is_last = i == n - 1
        is_end_word = is_first or is_last

        by_top = top_y - i * (BOX_H + GAP)
        by_bot = by_top - BOX_H

        # Fill
        if is_end_word:
            c.setFillColor(hex_colour(colour))
        elif show_answers:
            c.setFillColor(HexColor("#EEF6FB"))
        else:
            c.setFillColor(white)
        c.rect(bx, by_bot, BOX_W, BOX_H, fill=1, stroke=0)

        # Border
        c.setStrokeColor(hex_colour(colour))
        if is_end_word:
            c.setLineWidth(2)
            c.setDash()
        else:
            c.setLineWidth(1)
            c.setDash(4, 3)
        c.rect(bx, by_bot, BOX_W, BOX_H, fill=0, stroke=1)
        c.setDash()

        # Word / blank content
        if is_end_word or show_answers:
            fs = 16 if is_end_word else 13
            c.setFont("Helvetica-Bold", fs)
            c.setFillColor(white if is_end_word else hex_colour(colour))
            tw = c.stringWidth(word, "Helvetica-Bold", fs)
            c.drawString(bx + (BOX_W - tw) / 2, by_bot + (BOX_H - fs) / 2 + 1, word)

        # Hint clue (puzzle page only, middle rung only)
        if (not show_answers and not is_end_word
                and hint_idx is not None and i == hint_idx
                and hint_clue):
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(hex_colour(colour))
            clue_text = f"Clue: {hint_clue}"
            c.drawString(bx + BOX_W + STILE_OFFSET + 8, by_bot + BOX_H / 2 - 4, clue_text)

        # Stile connectors below this box (not below last)
        if i < n - 1:
            c.setStrokeColor(hex_colour(colour))
            c.setLineWidth(2.5)
            c.line(stile_left, by_bot, stile_left, by_bot - GAP)
            c.line(stile_right, by_bot, stile_right, by_bot - GAP)


def render_word_ladder_pdf(puzzle: dict, year_group: str = "Y4") -> bytes:
    colour = year_colour(year_group)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    path = puzzle["path"]
    topic = puzzle.get("topic", "")
    num_steps = puzzle["num_steps"]
    hint_idx = puzzle.get("hint_idx")
    hint_clue = puzzle.get("hint_clue", "")
    title = f"Word Ladder: {topic.title()}"

    for page in ("puzzle", "answers"):
        subtitle = (
            "Answers" if page == "answers"
            else f"Change one letter at a time — {num_steps} step{'s' if num_steps != 1 else ''}"
        )
        draw_header(c, title, subtitle, colour)
        draw_footer(c)

        top = content_top() - 6
        _draw_ladder(
            c, path, colour, top,
            show_answers=(page == "answers"),
            hint_idx=hint_idx if page == "puzzle" else None,
            hint_clue=hint_clue,
        )

        if page == "puzzle":
            n = len(path)
            bottom_y = top - n * (BOX_H + GAP) - 16
            c.setFont("Helvetica-Oblique", 9)
            c.setFillColorRGB(0.45, 0.45, 0.45)
            c.drawCentredString(
                PAGE_W / 2, bottom_y,
                "Change one letter on each rung. Every rung must be a real English word.",
            )

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
