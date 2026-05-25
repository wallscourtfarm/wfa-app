"""
Cloze Passage PDF renderer.
Page 1: passage with numbered blanks + optional word bank.
Page 2: complete passage (answer key).
"""
import io
import re
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

from .pdf_utils import (
    PAGE_W, PAGE_H, MARGIN, HEADER_H,
    year_colour, hex_colour,
    draw_header, draw_footer, content_top, content_bottom,
)

LINE_H = 14      # approx line height for passage text
PARA_FS = 11     # passage font size
BLANK_W = 70     # width of each blank underline


def _split_passage(passage_with_blanks: str) -> list[tuple[str, int | None]]:
    """
    Parse the passage into a list of (text, blank_num) segments.
    blank_num is None for plain text, or the blank number.
    """
    pattern = re.compile(r"___(\d+)___")
    segments = []
    last_end = 0
    for m in pattern.finditer(passage_with_blanks):
        if m.start() > last_end:
            segments.append((passage_with_blanks[last_end:m.start()], None))
        segments.append(("", int(m.group(1))))
        last_end = m.end()
    if last_end < len(passage_with_blanks):
        segments.append((passage_with_blanks[last_end:], None))
    return segments


def _draw_passage_with_blanks(
    c, segments: list[tuple], colour: str, blanks: list[str],
    top_y: float, answers: bool
) -> float:
    """
    Render the passage word-by-word, inserting numbered blanks where needed.
    Returns the y coordinate after the last line.
    """
    c.setFont("Helvetica", PARA_FS)
    c.setFillColor(black)

    line_max_x = PAGE_W - MARGIN
    x = MARGIN
    y = top_y
    line_h = PARA_FS + 5  # leading

    def new_line():
        nonlocal x, y
        x = MARGIN
        y -= line_h
        return y

    def draw_word(word, is_blank=False, blank_num=None):
        nonlocal x, y
        if is_blank and answers:
            text = blanks[blank_num - 1] if blank_num and blank_num <= len(blanks) else "?"
            c.setFont("Helvetica-Bold", PARA_FS)
            c.setFillColor(hex_colour(colour))
            tw = c.stringWidth(text, "Helvetica-Bold", PARA_FS)
            if x + tw > line_max_x:
                new_line()
            c.drawString(x, y, text)
            x += tw + 4
            c.setFont("Helvetica", PARA_FS)
            c.setFillColor(black)
        elif is_blank:
            # Draw underline with number above
            gap_w = max(BLANK_W, 8 * (len(blanks[blank_num - 1]) if blank_num and blank_num <= len(blanks) else 6))
            gap_w = min(gap_w, 100)
            if x + gap_w > line_max_x:
                new_line()
            # Underline
            c.setStrokeColor(hex_colour(colour))
            c.setLineWidth(1.2)
            c.line(x, y - 2, x + gap_w, y - 2)
            # Number above line
            c.setFont("Helvetica", 7)
            c.setFillColor(hex_colour(colour))
            num_text = f"({blank_num})"
            c.drawString(x + 2, y + 4, num_text)
            c.setFont("Helvetica", PARA_FS)
            c.setFillColor(black)
            x += gap_w + 6
        else:
            tw = c.stringWidth(word, "Helvetica", PARA_FS)
            if x + tw > line_max_x and x > MARGIN:
                new_line()
            c.drawString(x, y, word)
            x += tw

    for text, blank_num in segments:
        if blank_num is not None:
            draw_word("", is_blank=True, blank_num=blank_num)
        else:
            # Split plain text into tokens preserving spaces
            tokens = re.split(r"(\s+)", text)
            for tok in tokens:
                if tok.strip() == "":
                    # space: advance x a bit
                    x += c.stringWidth(" ", "Helvetica", PARA_FS) * (len(tok) or 1)
                    if x > line_max_x:
                        new_line()
                else:
                    draw_word(tok)
                    x += c.stringWidth(" ", "Helvetica", PARA_FS)

    return y - line_h


def _draw_word_bank(c, word_bank: list[str], colour: str, top_y: float) -> float:
    """Draw word bank box. Returns y below the box."""
    if not word_bank:
        return top_y

    box_margin = 6
    chip_h = 16
    chips_per_row = 5
    n_rows = -(-len(word_bank) // chips_per_row)  # ceiling div
    chip_w = (PAGE_W - 2 * MARGIN - (chips_per_row - 1) * box_margin) / chips_per_row
    box_h = n_rows * (chip_h + box_margin) + 24

    box_y = top_y - box_h

    # Background box
    c.setFillColor(HexColor("#EEF6FB"))
    c.rect(MARGIN, box_y, PAGE_W - 2 * MARGIN, box_h, fill=1, stroke=0)
    c.setStrokeColor(hex_colour(colour))
    c.setLineWidth(1)
    c.rect(MARGIN, box_y, PAGE_W - 2 * MARGIN, box_h, fill=0, stroke=1)

    # Label
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(hex_colour(colour))
    c.drawString(MARGIN + 6, top_y - 14, "Word bank:")

    # Chips
    for i, word in enumerate(word_bank):
        row = i // chips_per_row
        col = i % chips_per_row
        cx = MARGIN + col * (chip_w + box_margin)
        cy = top_y - 22 - row * (chip_h + box_margin) - chip_h

        c.setFillColor(white)
        c.setStrokeColor(hex_colour(colour))
        c.setLineWidth(0.8)
        c.roundRect(cx, cy, chip_w, chip_h, 3, fill=1, stroke=1)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(black)
        tw = c.stringWidth(word.title(), "Helvetica-Bold", 9)
        c.drawString(cx + (chip_w - tw) / 2, cy + 4, word.title())

    return box_y - 8


def render_cloze_pdf(puzzle: dict, year_group: str = "Y4") -> bytes:
    colour = year_colour(year_group)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    topic = puzzle.get("topic", "")
    passage_blanks = puzzle["passage_with_blanks"]
    passage_full = puzzle["passage_full"]
    blanks = puzzle["blanks"]
    word_bank = puzzle.get("word_bank", [])
    show_bank = puzzle.get("show_bank", True)
    title = f"Cloze Passage: {topic.title()}"

    segments = _split_passage(passage_blanks)

    for page in ("puzzle", "answers"):
        subtitle = "Answers" if page == "answers" else "Fill in the missing words"
        draw_header(c, title, subtitle, colour)
        draw_footer(c)

        top = content_top() - 4

        if page == "puzzle":
            after_text = _draw_passage_with_blanks(
                c, segments, colour, blanks, top, answers=False
            )
            if show_bank and word_bank:
                _draw_word_bank(c, word_bank, colour, after_text - 14)
        else:
            # Answer page: full passage in colour
            _draw_passage_with_blanks(
                c, segments, colour, blanks, top, answers=True
            )
            # Also list the blanks at the bottom
            ans_y = content_bottom() + 40
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(hex_colour(colour))
            c.drawString(MARGIN, ans_y, "Answers in order:")
            c.setFont("Helvetica", 9)
            c.setFillColor(black)
            answer_line = "  ".join(
                f"({i+1}) {w.title()}" for i, w in enumerate(blanks)
            )
            c.drawString(MARGIN, ans_y - 13, answer_line)

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
