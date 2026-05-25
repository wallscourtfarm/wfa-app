"""
Word Scramble PDF renderer.
Page 1: scrambled words with blank answer spaces.
Page 2: answers.
"""
import io
import math
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black

from .pdf_utils import (
    PAGE_W, PAGE_H, MARGIN, HEADER_H,
    year_colour, hex_colour,
    draw_header, draw_footer, content_top,
)

ROW_H = 28        # row height
COL_W_NUM = 24    # width of number column
COL_W_SCRAMBLE = 130
COL_W_GAP = 20
COL_W_ANSWER = 200


def _draw_table(c, items: list[dict], colour: str, top_y: float, answers: bool) -> None:
    """Draw scramble rows. items = list of {original, scrambled, blank_hint}."""
    n_cols = 2 if len(items) > 8 else 1
    col_block_w = (PAGE_W - 2 * MARGIN) / n_cols
    half = math.ceil(len(items) / n_cols)

    for col_idx in range(n_cols):
        start = col_idx * half
        chunk = items[start: start + half]
        base_x = MARGIN + col_idx * col_block_w

        y = top_y
        for i, item in enumerate(chunk):
            num = start + i + 1

            # Row background (alternating)
            if i % 2 == 0:
                c.setFillColor(HexColor("#F5FBFF"))
                c.rect(base_x, y - ROW_H, col_block_w - 8, ROW_H, fill=1, stroke=0)

            # Number
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(hex_colour(colour))
            c.drawString(base_x + 4, y - ROW_H + 9, f"{num}.")

            # Scrambled word
            scrambled = item["scrambled"]
            c.setFont("Helvetica-Bold", 13)
            c.setFillColor(black)
            c.drawString(base_x + COL_W_NUM, y - ROW_H + 8, scrambled)

            # Arrow
            c.setFont("Helvetica", 11)
            c.setFillColor(HexColor("#AAAAAA"))
            arrow_x = base_x + COL_W_NUM + COL_W_SCRAMBLE
            c.drawString(arrow_x, y - ROW_H + 8, "→")

            # Answer or blank hint
            ans_x = arrow_x + 20
            if answers:
                c.setFont("Helvetica-Bold", 13)
                c.setFillColor(hex_colour(colour))
                c.drawString(ans_x, y - ROW_H + 8, item["original"].title())
            else:
                # Draw one box per letter
                box_w = 16
                box_h = 18
                word_len = len(item["original"])
                for b in range(word_len):
                    bx = ans_x + b * (box_w + 2)
                    by = y - ROW_H + 5
                    c.setFillColor(white)
                    c.setStrokeColor(hex_colour(colour))
                    c.setLineWidth(0.8)
                    c.rect(bx, by, box_w, box_h, fill=1, stroke=1)
                    # For Easy: show first letter
                    hint = item["blank_hint"].replace(" ", "")
                    if b < len(hint) and hint[b] != "_":
                        c.setFont("Helvetica-Bold", 10)
                        c.setFillColor(hex_colour(colour))
                        lw = c.stringWidth(hint[b], "Helvetica-Bold", 10)
                        c.drawString(bx + (box_w - lw) / 2, by + 4, hint[b])

            y -= ROW_H + 2


def render_word_scramble_pdf(items: list[dict], topic: str, year_group: str = "Y4") -> bytes:
    colour = year_colour(year_group)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    title = f"Word Scramble: {topic.title()}"

    for page in ("puzzle", "answers"):
        subtitle = "Answers" if page == "answers" else "Unscramble each word and write it in the boxes"
        draw_header(c, title, subtitle, colour)
        draw_footer(c)

        top = content_top() - 4
        _draw_table(c, items, colour, top, answers=(page == "answers"))
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
