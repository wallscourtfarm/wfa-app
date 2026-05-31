"""
Word search PDF renderer.
Page 1: blank puzzle grid + word bank.
Page 2: answer grid with highlighted word cells.
"""
import io
import math
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, Color

from .pdf_utils import (
    PAGE_W, PAGE_H, MARGIN, HEADER_H, FOOTER_Y,
    YEAR_COLOURS, DEFAULT_COLOUR,
    hex_colour as _hex,
    draw_header, draw_footer, content_top, content_bottom,
)



def _draw_grid(c, grid, cell, gx, gy_top, colour, highlights=None):
    """
    Draw the grid. gy_top is the TOP of the grid in ReportLab coords (y increases upward).
    highlights: list of (row, col, dr, dc, word_len) — cells to shade on answer page.
    """
    n = len(grid)
    gw = n * cell
    gh = n * cell
    gy_bottom = gy_top - gh

    # White background
    c.setFillColorRGB(1, 1, 1)
    c.rect(gx, gy_bottom, gw, gh, fill=1, stroke=0)

    # Highlight answer cells — use a solid light tint (alpha not reliable in canvas)
    if highlights:
        hi = _hex(colour)
        # Blend colour toward white at 70% to make a visible but readable tint
        tint_r = hi.red   * 0.35 + 0.65
        tint_g = hi.green * 0.35 + 0.65
        tint_b = hi.blue  * 0.35 + 0.65
        c.setFillColorRGB(tint_r, tint_g, tint_b)
        for (wr, wc, dr, dc, wlen) in highlights:
            for i in range(wlen):
                r_i  = wr + dr * i
                c_i  = wc + dc * i
                cx   = gx + c_i * cell
                cy   = gy_top - (r_i + 1) * cell
                c.rect(cx, cy, cell, cell, fill=1, stroke=0)

    # Grid lines
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.4)
    for r in range(n + 1):
        y = gy_top - r * cell
        c.line(gx, y, gx + gw, y)
    for ci in range(n + 1):
        x = gx + ci * cell
        c.line(x, gy_bottom, x, gy_top)

    # Letters
    fs = cell * 0.46
    c.setFont("Helvetica-Bold", fs)
    c.setFillColor(black)
    for r, row in enumerate(grid):
        for ci, letter in enumerate(row):
            cx = gx + ci * cell
            cy = gy_top - (r + 1) * cell
            lw = c.stringWidth(letter, "Helvetica-Bold", fs)
            lx = cx + (cell - lw) / 2
            ly = cy + cell * 0.27
            c.drawString(lx, ly, letter)

    # Outer border
    c.setStrokeColor(_hex(colour))
    c.setLineWidth(2.0)
    c.rect(gx, gy_bottom, gw, gh, fill=0, stroke=1)

    return gy_bottom


def _draw_word_bank(c, words, y_top, colour):
    """Draw the word bank starting at y_top. Returns the bottom y coordinate."""
    c.setFillColor(_hex(colour))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN, y_top, "Find these words:")

    words_sorted = sorted(words, key=str.lower)
    usable_w = PAGE_W - 2 * MARGIN
    n_cols = 4 if len(words) >= 8 else (3 if len(words) >= 5 else 2)
    col_w = usable_w / n_cols
    row_h = 15

    c.setFont("Helvetica", 10)
    c.setFillColor(black)

    for i, word in enumerate(words_sorted):
        col = i % n_cols
        row = i // n_cols
        wx = MARGIN + col * col_w
        wy = y_top - 16 - row * row_h
        c.drawString(wx, wy, word.title())

    n_rows = math.ceil(len(words_sorted) / n_cols)
    return y_top - 16 - n_rows * row_h


def render_word_search_pdf(grid, words, word_positions, title, year_group="Y4"):
    """
    Build a two-page PDF.
    word_positions: list of (word, row, col, dr, dc) returned by generate_word_search().
    Returns bytes.
    """
    colour = YEAR_COLOURS.get(year_group, DEFAULT_COLOUR)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Pre-compute highlight data
    highlights = [
        (r, col, dr, dc, len(word))
        for (word, r, col, dr, dc) in word_positions
    ]

    for page in ("puzzle", "answers"):
        subtitle = "Answers" if page == "answers" else "Can you find all the words?"
        draw_header(c, title, subtitle, colour)
        draw_footer(c)

        top       = content_top()

        n = len(grid)
        usable_w  = PAGE_W - 2 * MARGIN

        # Fit the grid: use up to 68% of the remaining vertical space
        max_cell_w = usable_w / n
        max_cell_h = (content_bottom() - top) * 0.68 / n
        cell = min(max_cell_w, max_cell_h, 33)

        grid_w = n * cell
        gx     = (PAGE_W - grid_w) / 2      # centred

        hi = highlights if page == "answers" else None
        gy_bottom = _draw_grid(c, grid, cell, gx, top, colour, hi)

        # Word bank below grid with a small gap
        _draw_word_bank(c, words, gy_bottom - 14, colour)

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
