"""
Shared PDF helpers — header, footer, colour utilities.
Import from here in each puzzle PDF module.
"""
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black

# ── WFA brand colours (inlined from wfa_shared.brand) ────────────────────────
YEAR_COLOURS = {
    "Y1": "#e57d24", "Y2": "#2bae62", "Y3": "#c0157b",
    "Y4": "#1798d3", "Y5": "#e57d24", "Y6": "#2bae62",
}
DEFAULT_COLOUR = "#1798d3"

def year_colour(year_group: str) -> str:
    return YEAR_COLOURS.get(year_group, DEFAULT_COLOUR)

PAGE_W, PAGE_H = A4
MARGIN = 38
HEADER_H = 50
FOOTER_Y = 14


def hex_colour(s: str) -> HexColor:
    return HexColor(s)


def draw_header(c, title: str, subtitle: str, colour: str) -> None:
    """Filled colour header bar with title, subtitle and school name."""
    c.setFillColor(hex_colour(colour))
    c.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(MARGIN, PAGE_H - HEADER_H + 20, title)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, PAGE_H - HEADER_H + 7, subtitle)
    label = "Wallscourt Farm Academy"
    c.setFont("Helvetica-Bold", 8)
    lw = c.stringWidth(label, "Helvetica-Bold", 8)
    c.drawString(PAGE_W - MARGIN - lw, PAGE_H - HEADER_H + 28, label)


def draw_footer(c) -> None:
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    c.drawCentredString(PAGE_W / 2, FOOTER_Y, "wallscourtfarm.github.io  ·  Word Puzzle Generator")


def content_top() -> float:
    """Y coordinate just below the header with a small gap."""
    return PAGE_H - HEADER_H - 18


def content_bottom() -> float:
    """Y coordinate just above the footer area."""
    return FOOTER_Y + 20