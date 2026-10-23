"""spelling_practice_pdf.py — Key spelling practice sheets in the handwriting format.

For children who have been handed the same key spelling for several weeks (data_manager.stuck_key_spellings).
One compact sheet per child, laid out like the Precision Teaching sheets: a slim header (initials | title | week,
date on the right, thin blue rule), a one-line instruction, then one ruled row per word with the word in dotted
writing to trace and keep writing, followed by empty ruled row(s) to write it from memory. A sheet that fits in
half a page shares the page with the next child's (dashed cut line between), so a class prints on little paper.

Fonts, sizes and line geometry come from handwriting_sheet.py (the school handwriting tool): XCCW cursive dotted
or solid, Sassoon Infant dotted, Linkpen pre-cursive dotted. The header carries the child's INITIALS and a name
slot (stamps.py); the real name is written in the teacher's browser.
"""
import io
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import handwriting_sheet as hs
import stamps

MM = 72 / 25.4
W, H = A4
MARGIN = 12 * MM
USABLE_W = W - 2 * MARGIN
ROW_GAP = 2.5 * MM        # between the descender line of one row and the top line of the next
WORD_GAP = 2.0 * MM       # extra space after each word block
HEADER_H = 9 * MM
INSTR_H = 5.5 * MM
CUT_GAP = 6 * MM

NAVY = (14 / 255, 40 / 255, 65 / 255)
TEAL = (21 / 255, 96 / 255, 130 / 255)
GREY = (0.45, 0.45, 0.45)
LBLUE = (0.65, 0.82, 0.93)
WFA_BLUE = (0x17 / 255, 0x98 / 255, 0xd3 / 255)

FONT_CHOICES = [('xccw', 'Cursive, dotted (XCCW)'), ('xccw_solid', 'Cursive, solid (XCCW)'),
                ('sassoon', 'Print, dotted (Sassoon)'), ('linkpen', 'Pre-cursive, dotted (Linkpen)')]
DEFAULT_FONT = 'xccw'
INSTRUCTION = 'Trace each word, then keep writing it to the end of the line. Write it from memory on the empty line.'


def _spec(font_key):
    """Ascender/descender/x-height geometry, font size, draw and measure functions for a font choice."""
    hs._ensure_fonts()
    if font_key == 'sassoon':
        return dict(asc=hs.SASS_ASCEND, desc=hs.SASS_DESCEND, xh=hs.SASS_XHEIGHT, fs=hs.SASS_FS,
                    draw=hs._draw_sassoon, width=lambda t: hs._sass_text_width(t, hs.SASS_FS))
    if font_key == 'linkpen':
        return dict(asc=hs.LINK_ASCEND, desc=hs.LINK_DESCEND, xh=hs.LINK_XHEIGHT, fs=hs.LINK_FS,
                    draw=hs._draw_linkpen, width=lambda t: hs._link_text_width(t, hs.LINK_FS))
    solid = font_key == 'xccw_solid'
    return dict(asc=hs.XCCW_ASCEND, desc=hs.XCCW_DESCEND, xh=hs.XCCW_XHEIGHT, fs=hs.XCCW_FS,
                draw=lambda c, x, y, t, s: hs._draw_xccw(c, x, y, t, s, solid=solid),
                width=lambda t: hs._xccw_text_width(t, solid=solid, size=hs.XCCW_FS))


def _ruled_row(c, baseline, spec, show_x=True, show_desc=True):
    asc, desc = spec['asc'], spec['desc']
    c.setDash()
    c.setStrokeColorRGB(*LBLUE)
    c.setLineWidth(0.5)
    c.line(MARGIN, baseline + asc, MARGIN + USABLE_W, baseline + asc)
    if show_x:
        c.setStrokeColorRGB(0.80, 0.80, 0.80)
        c.setLineWidth(0.4)
        c.setDash(3, 3)
        c.line(MARGIN, baseline + spec['xh'], MARGIN + USABLE_W, baseline + spec['xh'])
        c.setDash()
    c.setStrokeColorRGB(*LBLUE)
    c.setLineWidth(1.4)
    c.line(MARGIN, baseline, MARGIN + USABLE_W, baseline)
    if show_desc:
        c.setStrokeColorRGB(0.80, 0.80, 0.80)
        c.setLineWidth(0.4)
        c.setDash(8, 4)
        c.line(MARGIN, baseline - desc, MARGIN + USABLE_W, baseline - desc)
        c.setDash()


def _header(c, y_top, label, pupil_id, title, right_text, continued=False):
    """Slim one-line header: initials | title (name slot for the browser), date on the right, blue rule."""
    size = 11
    baseline = y_top - HEADER_H * 0.62
    post = '  |  ' + title + ('  (continued)' if continued else '')
    c.setFont('Helvetica-Bold', size)
    c.setFillColorRGB(*NAVY)
    c.drawString(MARGIN, baseline, label + post)
    stamps.log(c, MARGIN, baseline, label, size, pupil_id, post=post, color=NAVY)
    if right_text:
        c.setFont('Helvetica', 9)
        c.setFillColorRGB(*GREY)
        c.drawRightString(MARGIN + USABLE_W, baseline, right_text)
    c.setStrokeColorRGB(*WFA_BLUE)
    c.setLineWidth(1.3)
    c.line(MARGIN, y_top - HEADER_H, MARGIN + USABLE_W, y_top - HEADER_H)
    return y_top - HEADER_H


def _block_height(n_words, spec, practice_lines):
    row_h = spec['asc'] + spec['desc'] + ROW_GAP
    return HEADER_H + INSTR_H + n_words * ((1 + practice_lines) * row_h + WORD_GAP)


def _draw_child(c, slot_top, slot_bottom, child, spec, practice_lines, title, right_text, show_x, show_desc):
    """Draw one child's sheet into [slot_bottom, slot_top]. Words that do not fit carry on to a new full page.
    Returns True if a new page was started (so the caller's page state is 'empty' again)."""
    row_h = spec['asc'] + spec['desc'] + ROW_GAP
    new_page = False
    y_top = _header(c, slot_top, child['label'], child.get('pupil_id'), title, right_text)
    c.setFillColorRGB(*TEAL)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(MARGIN, y_top - 11, INSTRUCTION)
    y = y_top - INSTR_H - 2 - spec['asc']
    bottom = slot_bottom
    for item in child['words']:
        need = (1 + practice_lines) * row_h + WORD_GAP
        if y + spec['asc'] - need < bottom - WORD_GAP:
            c.showPage()
            new_page = True
            y_top = _header(c, H - MARGIN, child['label'], child.get('pupil_id'), title, right_text, continued=True)
            y = y_top - 4 - spec['asc']
            bottom = MARGIN
        word = item['word'] if isinstance(item, dict) else str(item)
        _ruled_row(c, y, spec, show_x, show_desc)
        spec['draw'](c, MARGIN + 2, y, word, spec['fs'])     # once only: the child keeps writing it along the line
        y -= row_h
        for _ in range(practice_lines):
            _ruled_row(c, y, spec, show_x, show_desc)
            y -= row_h
        y -= WORD_GAP
    c.setFillColorRGB(0, 0, 0)
    return new_page


def build_practice_sheets(children, font_key=DEFAULT_FONT, practice_lines=1, week_ref='', title='Key spellings practice',
                          show_x=True, show_desc=True):
    """children: [{'label': initials, 'pupil_id', 'words': [{'word', 'n', 'weeks'} or str, ...]}]. Returns PDF bytes.
    Call stamps.begin() before and stamps.finish() after, so the browser can write the real names."""
    spec = _spec(font_key)
    practice_lines = max(0, min(3, int(practice_lines or 0)))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(title)
    right_text = f"Date: {datetime.date.today().strftime('%d/%m/%y')}"
    full_title = f"{title}  |  {week_ref}" if week_ref else title
    usable_h = H - 2 * MARGIN
    half_h = (usable_h - CUT_GAP) / 2
    top = H - MARGIN
    state = 'empty'          # 'empty' or 'half' (top slot of the current page is used)
    # Half-page sheets first (two to a page), then the full-page ones, so no half page is left blank.
    children = [ch for ch in children if ch.get('words')]
    halves = [ch for ch in children if _block_height(len(ch['words']), spec, practice_lines) <= half_h]
    fulls = [ch for ch in children if ch not in halves]
    for child in halves + fulls:
        fits_half = child in halves
        if not fits_half:
            if state == 'half':
                c.showPage()
                state = 'empty'
            _draw_child(c, top, MARGIN, child, spec, practice_lines, full_title, right_text, show_x, show_desc)
            c.showPage()
            state = 'empty'
            continue
        if state == 'empty':
            _draw_child(c, top, top - half_h, child, spec, practice_lines, full_title, right_text, show_x, show_desc)
            state = 'half'
        else:
            cut_y = top - half_h - CUT_GAP / 2
            c.setDash([4, 3], 0)
            c.setStrokeColorRGB(0.55, 0.55, 0.55)
            c.setLineWidth(0.8)
            c.line(MARGIN, cut_y, MARGIN + USABLE_W, cut_y)
            c.setDash()
            _draw_child(c, top - half_h - CUT_GAP, MARGIN, child, spec, practice_lines, full_title, right_text, show_x, show_desc)
            c.showPage()
            state = 'empty'
    if state == 'half':
        c.showPage()
    c.save()
    return buf.getvalue()
