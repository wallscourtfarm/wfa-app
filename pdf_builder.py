"""
WFA Spelling PDF Builder
Generates all print-ready documents using ReportLab.

Functions:
  build_spelling_pages(pupils, rule, rule_words, week_ref)  → bytes (zip of per-child A5 PDFs)
  build_paired_word_lists(pupils, week_ref)                 → bytes (PDF)
  build_recording_sheet(pupils, week_ref)                   → bytes (PDF)
  build_tt_check_sheet(pupils, week_ref)                    → bytes (PDF)
"""

import io
import os
import zipfile
import random
from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Sassoon Infant if available (stored in fonts/ in the repo)
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
_SASSOON_PATH = os.path.join(_FONT_DIR, 'SassoonInfant.ttf')
if os.path.exists(_SASSOON_PATH):
    pdfmetrics.registerFont(TTFont('SassoonInfant', _SASSOON_PATH))
    SASSOON = 'SassoonInfant'
else:
    SASSOON = 'Helvetica'  # fallback
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# ── Brand colours ──────────────────────────────────────────────────────────
BLUE  = (23/255, 152/255, 211/255)   # #1798d3
NAVY  = (26/255, 60/255, 110/255)    # #1A3C6E
GOLD  = (232/255, 184/255, 75/255)   # #E8B84B
WHITE = (1, 1, 1)
LGREY = (0.92, 0.92, 0.92)
DGREY = (0.4, 0.4, 0.4)
BLACK = (0, 0, 0)

TT_ORDER = ["10","2","5","4","8","3","6","9","7","11","12","All"]

def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))

# ── Spelling page (A5 portrait, one per child) ─────────────────────────────

def build_spelling_page(pupil, rule_title, rule_words, key_words, week_ref):
    """
    Returns bytes for a single child's A5 spelling page.
    Matches the home learning format from the example PDF.
    """
    buf = io.BytesIO()
    W, H = A5
    M = 10 * mm
    UW = W - 2 * M
    c = canvas.Canvas(buf, pagesize=A5)

    # ── Header bar ──────────────────────────────────────────────────────
    c.setFillColorRGB(*BLUE)
    c.rect(0, H - 14*mm, W, 14*mm, fill=1, stroke=0)
    c.setFillColorRGB(*WHITE)
    c.setFont("Helvetica-Bold", 9)
    name = pupil.get("first", "") + (" " + pupil["last"] if pupil.get("last") else "")
    c.drawString(M, H - 9*mm, f"{week_ref} – Home Learning – {name}")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - M, H - 9*mm, "Personal Key Spellings and Weekly Spelling Rule Words")

    cy = H - 18*mm

    # ── Spelling Shed login ─────────────────────────────────────────────
    ss_user = pupil.get("ss_user", "")
    ss_pass = pupil.get("ss_pass", "")
    if ss_user or ss_pass:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(*NAVY)
        c.drawString(M, cy, f"Spelling Shed  –  {ss_user} / {ss_pass}")
        cy -= 6*mm

    # ── Instruction text ────────────────────────────────────────────────
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(*DGREY)
    line1 = "The first 5 words below are your Key Spellings."
    line2 = f"This week's spelling rule – {rule_title}."
    line3 = "Practise spelling these words. Write each word within a sentence in the space"
    line4 = "below. These words will be checked in your paired spelling bee."
    for line in [line1, line2, line3, line4]:
        c.drawString(M, cy, line)
        cy -= 4.5*mm
    cy -= 2*mm

    # ── Word list ───────────────────────────────────────────────────────
    all_words = list(key_words) + list(rule_words)
    line_h = (cy - M - 4*mm) / max(len(all_words), 1)
    line_h = min(line_h, 14*mm)

    for i, word in enumerate(all_words):
        # Divider between key spellings and rule words
        if i == 5:
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.setLineWidth(0.3)
            c.setDash(2, 2)
            c.line(M, cy + line_h*0.7, W - M, cy + line_h*0.7)
            c.setDash()

        # Word
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(*NAVY)
        c.drawString(M, cy, word)

        # Writing line
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.5)
        c.line(M + 28*mm, cy - 1*mm, W - M, cy - 1*mm)

        cy -= line_h

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def build_all_spelling_pages(pupils, rule_title, rule_words, key_words_map, week_ref):
    """
    Returns a ZIP of per-child spelling page PDFs.
    key_words_map: {pupil_id: [word1..word5]}
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in pupils:
            kw = key_words_map.get(p["id"], [])
            rw = rule_words
            pdf = build_spelling_page(p, rule_title, rw, kw, week_ref)
            fname = f"Spelling_{week_ref}_{p['first'].replace(' ','_')}.pdf"
            zf.writestr(fname, pdf)
    buf.seek(0)
    return buf.read()


# ── Paired word lists ──────────────────────────────────────────────────────

def build_paired_word_lists(pupils, main_rule_words, rev_rule_words,
                             key_words_map, week_ref, print_order='partner_pairs'):
    """
    A4 portrait. 4 columns × 3 rows = 12 cards per page.
    Coloured header = pair colour + IM/WU class badge.
    Words 1–5: key spellings. Words 6–10: rule words, separated by a line.

    print_order:
      'partner_pairs' – interleaved A/B pages so same-position cards on
                        consecutive pages are partners (page 1 & 2, 3 & 4 …)
      'by_class'      – IM pupils first then WU, alphabetical by first name
      'all'           – all pupils alphabetical by first name
    """
    buf = io.BytesIO()
    W, H = A4
    M  = 6 * mm
    c  = canvas.Canvas(buf, pagesize=A4)

    COLS    = 4
    ROWS    = 3
    col_w   = (W - 2*M) / COLS
    row_h   = (H - 2*M) / ROWS
    GAP     = 6          # pt gap between cards (visible cut margin)

    def draw_card(cx, cy, pupil, partner_name, words, colour_hex, colour_name=""):
        """cx/cy = top-left corner of card slot."""
        x = cx + GAP
        y = cy - row_h + GAP
        w = col_w - 2*GAP
        h = row_h - 2*GAP

        col_rgb  = _hex_to_rgb(colour_hex) if colour_hex else BLUE
        cls_lbl  = pupil.get("cls","")

        # ── Card border ───────────────────────────────────────────
        c.setStrokeColorRGB(*col_rgb)
        c.setLineWidth(2.0)
        c.rect(x, y, w, h, fill=0, stroke=1)

        # ── Header bar — solid colour ─────────────────────────────
        HDR = 10 * mm
        c.setFillColorRGB(*col_rgb)
        c.rect(x, y + h - HDR, w, HDR, fill=1, stroke=0)

        # Redraw top portion of border over header
        c.setStrokeColorRGB(*col_rgb)
        c.setLineWidth(2.0)
        c.rect(x, y, w, h, fill=0, stroke=1)

        # Name pill — white rounded rect, navy text
        PILL_H   = 7 * mm
        PILL_PAD = 2.5 * mm
        name     = pupil.get("first", "")
        c.setFont("Helvetica-Bold", 10)
        name_w   = c.stringWidth(name, "Helvetica-Bold", 10)
        pill_w   = name_w + 2 * PILL_PAD
        pill_x   = x + 2 * mm
        pill_y   = y + h - HDR + (HDR - PILL_H) / 2
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(pill_x, pill_y, pill_w, PILL_H, 3, fill=1, stroke=0)
        c.setFillColorRGB(*NAVY)
        c.drawString(pill_x + PILL_PAD, pill_y + PILL_H * 0.28, name)

        # Class badge pill — white rounded rect, navy text
        if cls_lbl:
            c.setFont("Helvetica-Bold", 8)
            badge_w  = c.stringWidth(cls_lbl, "Helvetica-Bold", 8) + 2 * PILL_PAD
            badge_x  = x + w - badge_w - 2 * mm
            badge_y  = pill_y
            c.setFillColorRGB(1, 1, 1)
            c.roundRect(badge_x, badge_y, badge_w, PILL_H, 3, fill=1, stroke=0)
            c.setFillColorRGB(*NAVY)
            c.drawCentredString(badge_x + badge_w / 2, badge_y + PILL_H * 0.28, cls_lbl)

        # ── Words ─────────────────────────────────────────────────
        GAP_AFTER_HDR = 14         # pt clearance between header and first word baseline
        word_h   = 20                  # fixed leading — tighter than auto-distributed
        wy       = y + h - HDR - GAP_AFTER_HDR - word_h * 0.2

        for i, word in enumerate(words[:10]):
            # Divider before word 6
            if i == 5:
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.setLineWidth(0.3)
                c.setDash(3, 2)
                c.line(x + 1*mm, wy + word_h * 0.85, x + w - 1*mm, wy + word_h * 0.85)
                c.setDash()

            c.setFont(SASSOON, 14)
            c.setFillColorRGB(*NAVY if i < 5 else (0.25, 0.25, 0.5))
            c.drawString(x + 2*mm, wy, f"{i+1}.  {word}")
            wy -= word_h

        # Colour name label at bottom-right corner
        if colour_name:
            r, g, b = col_rgb
            lum = 0.299*r + 0.587*g + 0.114*b
            label_col = (1,1,1) if lum < 0.55 else (0.15, 0.15, 0.15)
            c.setFillColorRGB(*col_rgb)
            lbl_h = 5 * mm
            c.rect(x, y, w, lbl_h, fill=1, stroke=0)
            c.setFillColorRGB(*label_col)
            c.setFont("Helvetica-Bold", 7)
            c.drawRightString(x + w - 2*mm, y + lbl_h * 0.3, colour_name)

    pupil_map = {p["id"]: p for p in pupils}

    def draw_cut_lines_bee():
        c.setStrokeColorRGB(0.35, 0.35, 0.35)
        c.setLineWidth(0.75)
        c.setDash(6, 4)
        for ci in range(0, COLS + 1):
            lx = M + ci * col_w
            c.line(lx, 0, lx, H)
        for ri in range(0, ROWS + 1):
            ly = H - M - ri * row_h
            c.line(0, ly, W, ly)
        c.setDash()

    # ── Separate into partner-A / partner-B / unpaired ────────────────
    # Partners A and B are drawn in separate page runs so that same-slot
    # positions on consecutive pages are auto-paired when stacked after printing.
    partners_a, partners_b, unpaired = [], [], []
    seen = set()
    for p in pupils:
        pid = p["id"]
        if pid in seen:
            continue
        pair_id = p.get("pair_id", "")
        if pair_id and pair_id in pupil_map:
            partners_a.append(p)
            partners_b.append(pupil_map[pair_id])
            seen.add(pid)
            seen.add(pair_id)
        else:
            unpaired.append(p)

    def _draw_batch(batch):
        drawn = 0
        for p in batch:
            page_pos = drawn % (COLS * ROWS)
            if drawn > 0 and page_pos == 0:
                draw_cut_lines_bee()
                c.showPage()
            partner    = pupil_map.get(p.get("pair_id",""), {})
            partner_nm = partner.get("first","") if partner else ""
            kw     = list(key_words_map.get(p["id"], []))[:5]
            rw     = list(rev_rule_words if p.get("group")=="revision" else main_rule_words)[:5]
            colour   = p.get("pair_colour","") or "#1798d3"
            col_name = p.get("pair_colour_name","")
            # Fallback: look up name from PAIR_COLOURS in class_manager if not stored
            if not col_name and colour:
                try:
                    from routes.class_manager import PAIR_COLOURS as _PC
                    col_name = next((pc['name'] for pc in _PC
                                     if pc['hex'].upper() == colour.upper()), '')
                except Exception:
                    pass
            col_idx = page_pos % COLS
            row_idx = page_pos // COLS
            cx = M + col_idx * col_w
            cy = H - M - row_idx * row_h
            draw_card(cx, cy, p, partner_nm, kw + rw, colour, col_name)
            drawn += 1
        if drawn:
            draw_cut_lines_bee()
            c.showPage()

    if print_order in ('by_class', 'all'):
        # Re-sort all pupils and print in one flat run (A then B still, but sorted)
        if print_order == 'by_class':
            # Sort by class abbreviation (IM before WU lexicographically), then first name
            def _cls_sort(p):
                cls_abbr = (p.get('cls') or p.get('file_cls') or '').split('_')[-1]
                return (cls_abbr, (p.get('first') or '').lower())
            sorted_pupils = sorted(pupils, key=_cls_sort)
        else:
            sorted_pupils = sorted(pupils, key=lambda p: (p.get('first') or '').lower())

        # Rebuild A/B split preserving pair structure but in the new order
        seen2 = set()
        pa2, pb2, up2 = [], [], []
        for p in sorted_pupils:
            pid = p['id']
            if pid in seen2:
                continue
            pair_id = p.get('pair_id', '')
            if pair_id and pair_id in pupil_map:
                pa2.append(p)
                pb2.append(pupil_map[pair_id])
                seen2.add(pid)
                seen2.add(pair_id)
            else:
                up2.append(p)
        _draw_batch(pa2)
        _draw_batch(pb2)
        _draw_batch(up2)
    else:
        # 'partner_pairs': interleave A and B pages so page N and page N+1
        # have the same pairs in the same grid positions — cut and match instantly.
        PER_PAGE = COLS * ROWS
        a_chunks = [partners_a[i:i+PER_PAGE] for i in range(0, len(partners_a), PER_PAGE)] if partners_a else []
        b_chunks = [partners_b[i:i+PER_PAGE] for i in range(0, len(partners_b), PER_PAGE)] if partners_b else []
        for i in range(max(len(a_chunks), len(b_chunks))):
            if i < len(a_chunks):
                _draw_batch(a_chunks[i])
            if i < len(b_chunks):
                _draw_batch(b_chunks[i])
        _draw_batch(unpaired)

    c.save()
    buf.seek(0)
    return buf.read()


# ── Double-sided bee cards ─────────────────────────────────────────────────

def build_double_sided_bee_pdf(pupils, main_rule_words, rev_rule_words,
                                key_words_map, week_ref):
    """
    A4 portrait. 2 columns × 4 rows = 8 cards per side.

    Front pages: partner-A cards.
    Back pages:  partner-B cards with columns mirrored left↔right so that,
                 when the sheet is flipped on its long edge (standard duplex),
                 every card lands directly behind its partner.

    Page order: front-1, back-1, front-2, back-2, … so the printer
    just needs "print both sides" selected.
    """
    buf = io.BytesIO()
    W, H = A4
    M = 6 * mm
    c = canvas.Canvas(buf, pagesize=A4)

    COLS    = 2
    ROWS    = 4
    PER_PG  = COLS * ROWS          # 8 cards per page
    col_w   = (W - 2 * M) / COLS
    row_h   = (H - 2 * M) / ROWS
    CGAP    = 5 * mm               # white padding between cut line and card edge

    # ── Card drawing ──────────────────────────────────────────────────────
    def draw_card_ds(cx, cy, pupil, words, colour_hex, colour_name=''):
        """cx/cy = top-left corner of the cell slot on the page."""
        x = cx + CGAP
        y = cy - row_h + CGAP
        w = col_w - 2 * CGAP
        h = row_h - 2 * CGAP

        col_rgb = _hex_to_rgb(colour_hex) if colour_hex else BLUE
        cls_lbl = (pupil.get('cls') or '').split('_')[-1]   # 'IM' or 'WU'
        name    = pupil.get('first', '')

        # Card border
        c.setStrokeColorRGB(*col_rgb)
        c.setLineWidth(2.0)
        c.rect(x, y, w, h, fill=0, stroke=1)

        # Coloured header bar
        HDR = 9 * mm
        c.setFillColorRGB(*col_rgb)
        c.rect(x, y + h - HDR, w, HDR, fill=1, stroke=0)
        # Redraw border on top
        c.setStrokeColorRGB(*col_rgb)
        c.setLineWidth(2.0)
        c.rect(x, y, w, h, fill=0, stroke=1)

        # Name pill
        PILL_H   = 6.5 * mm
        PILL_PAD = 2.5 * mm
        c.setFont('Helvetica-Bold', 11)
        name_w = c.stringWidth(name, 'Helvetica-Bold', 11)
        pill_w = name_w + 2 * PILL_PAD
        pill_x = x + 2 * mm
        pill_y = y + h - HDR + (HDR - PILL_H) / 2
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(pill_x, pill_y, pill_w, PILL_H, 3, fill=1, stroke=0)
        c.setFillColorRGB(*NAVY)
        c.drawString(pill_x + PILL_PAD, pill_y + PILL_H * 0.28, name)

        # Class badge pill
        if cls_lbl:
            c.setFont('Helvetica-Bold', 9)
            badge_w = c.stringWidth(cls_lbl, 'Helvetica-Bold', 9) + 2 * PILL_PAD
            badge_x = x + w - badge_w - 2 * mm
            c.setFillColorRGB(1, 1, 1)
            c.roundRect(badge_x, pill_y, badge_w, PILL_H, 3, fill=1, stroke=0)
            c.setFillColorRGB(*NAVY)
            c.drawCentredString(badge_x + badge_w / 2, pill_y + PILL_H * 0.28, cls_lbl)

        # ── Words area ────────────────────────────────────────────────────
        FOOTER_H    = 7 * mm
        TOP_PAD     = 3 * mm
        words_top   = y + h - HDR - TOP_PAD
        words_bot   = y + FOOTER_H + 2 * mm
        words_h     = words_top - words_bot
        word_row_h  = words_h / 5

        half_w = w / 2

        # Horizontal ruled lines between word rows
        c.setStrokeColorRGB(0.82, 0.82, 0.82)
        c.setLineWidth(0.4)
        for ri in range(1, 5):
            ly = words_bot + ri * word_row_h
            c.line(x + 2 * mm, ly, x + w - 2 * mm, ly)

        # Vertical separator between word columns
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.5)
        c.line(x + half_w, words_bot + mm, x + half_w, words_top - mm)

        # Draw words: left col = key words (1-5), right col = rule words (1-5)
        key_words_list  = words[:5]
        rule_words_list = words[5:10]
        NUM_FONT_SZ  = 9
        WORD_FONT_SZ = 16

        for col_i, (col_x_base, word_list, num_offset) in enumerate(
                [(x + 3 * mm, key_words_list, 0),
                 (x + half_w + 3 * mm, rule_words_list, 5)]):
            for wi, word in enumerate(word_list):
                # Baseline: centre of the word row
                wy = words_bot + (4 - wi) * word_row_h + word_row_h * 0.3
                # Number in small grey
                c.setFont('Helvetica', NUM_FONT_SZ)
                c.setFillColorRGB(0.5, 0.5, 0.5)
                num_str = f'{wi + 1 + num_offset}.'
                num_w   = c.stringWidth(num_str, 'Helvetica', NUM_FONT_SZ)
                c.drawString(col_x_base, wy, num_str)
                # Word in Sassoon
                c.setFont(SASSOON, WORD_FONT_SZ)
                c.setFillColorRGB(*NAVY)
                c.drawString(col_x_base + num_w + 2, wy, word)

        # Footer text
        c.setFont('Helvetica-Oblique', 6.5)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawCentredString(x + half_w, y + 2.2 * mm,
                            "Your partner's words are on the other side")

    # ── Cut lines ─────────────────────────────────────────────────────────
    def draw_cut_lines_ds():
        c.setStrokeColorRGB(0.35, 0.35, 0.35)
        c.setLineWidth(0.75)
        c.setDash(6, 4)
        for ci in range(COLS + 1):
            lx = M + ci * col_w
            c.line(lx, 0, lx, H)
        for ri in range(ROWS + 1):
            ly = H - M - ri * row_h
            c.line(0, ly, W, ly)
        c.setDash()

    # ── Build lookup and group pupils by class ────────────────────────────
    pupil_map = {p['id']: p for p in pupils}

    # Preserve class order as encountered (IM before WU in typical load order)
    by_class = {}
    class_order = []
    for p in pupils:
        cls_key = p.get('cls') or p.get('file_cls') or ''
        if cls_key not in by_class:
            by_class[cls_key] = []
            class_order.append(cls_key)
        by_class[cls_key].append(p)

    def _get_words(p):
        kw = list(key_words_map.get(p['id'], []))[:5]
        rw = list(rev_rule_words if p.get('group') == 'revision'
                  else main_rule_words)[:5]
        return kw + rw

    def _get_colour(p):
        colour = p.get('pair_colour', '') or '#1798d3'
        col_name = p.get('pair_colour_name', '')
        if not col_name and colour:
            try:
                from routes.class_manager import PAIR_COLOURS as _PC
                col_name = next(
                    (pc['name'] for pc in _PC
                     if pc['hex'].upper() == colour.upper()), '')
            except Exception:
                pass
        return colour, col_name

    # Horizontal nudge applied to back (mirrored) pages to compensate for
    # printer duplex registration drift.  Positive = shift right, negative = left.
    # Tune this after a test print — typical range is ±1–4 mm.
    BACK_OFFSET_X = 0 * mm

    # ── Page renderer ─────────────────────────────────────────────────────
    def draw_page(chunk, mirror_cols=False, cut_lines=True):
        """Render up to PER_PG cards. mirror_cols swaps left↔right within each row."""
        if not chunk:
            return
        # Build display order: optionally mirror columns within each row
        display = []
        for row in range(ROWS):
            row_cards = chunk[row * COLS:(row + 1) * COLS]
            if mirror_cols:
                # Pad to COLS width so empty slots stay correct after reversing
                padded = row_cards + [None] * (COLS - len(row_cards))
                display.extend(reversed(padded))
            else:
                display.extend(row_cards)

        if mirror_cols and BACK_OFFSET_X:
            c.saveState()
            c.translate(BACK_OFFSET_X, 0)

        for pos, pupil in enumerate(display):
            if pupil is None:
                continue
            col_idx = pos % COLS
            row_idx = pos // COLS
            cx = M + col_idx * col_w
            cy = H - M - row_idx * row_h
            colour, col_name = _get_colour(pupil)
            draw_card_ds(cx, cy, pupil, _get_words(pupil), colour, col_name)

        if cut_lines:
            draw_cut_lines_ds()

        if mirror_cols and BACK_OFFSET_X:
            c.restoreState()

        c.showPage()

    # ── Emit pages per class so each class starts on a fresh sheet ───────
    for cls_key in class_order:
        cls_pupils = by_class[cls_key]
        seen = set()
        pa, pb, unpaired = [], [], []
        for p in cls_pupils:
            pid = p['id']
            if pid in seen:
                continue
            pair_id = p.get('pair_id', '')
            if pair_id and pair_id in pupil_map:
                pa.append(p)
                pb.append(pupil_map[pair_id])
                seen.add(pid)
                seen.add(pair_id)
            else:
                unpaired.append(p)

        # Paired pupils — each chunk of PER_PG gets its own front+back sheet.
        # Partial last chunk leaves empty slots at the bottom (class-safe gap).
        for i in range(0, len(pa), PER_PG):
            draw_page(pa[i:i + PER_PG], mirror_cols=False, cut_lines=True)
            draw_page(pb[i:i + PER_PG], mirror_cols=True,  cut_lines=False)

        # Unpaired pupils from this class (front only)
        for i in range(0, len(unpaired), PER_PG):
            draw_page(unpaired[i:i + PER_PG], mirror_cols=False, cut_lines=True)

    c.save()
    buf.seek(0)
    return buf.read()


# ── Recording sheet ────────────────────────────────────────────────────────

def build_recording_sheet(pupils, week_ref):
    """
    A4 portrait. 6 cards per page (2×3), dashed cut lines.
    Each card: Name header row + 10 word rows (number | word blank | mark 1/0).
    """
    buf = io.BytesIO()
    PW, PH = A4
    c = canvas.Canvas(buf, pagesize=A4)

    PAD    = 5
    HALF_W = PW / 2
    THIRD_H = PH / 3

    NUM_W  = 22    # number column
    MARK_W = 44    # mark column
    HDR_H  = 22    # header row height
    ROW_H  = (THIRD_H - HDR_H - 2*PAD) / 10

    def draw_quadrant(qx, qy, pupil):
        """Draw one recording card. qx/qy = bottom-left corner of card."""
        # Outer border
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.setLineWidth(0.8)
        c.rect(qx + PAD, qy + PAD, HALF_W - 2*PAD, THIRD_H - 2*PAD, fill=0, stroke=1)

        bx = qx + PAD           # box left
        bw = HALF_W - 2*PAD     # box width
        by = qy + PAD           # box bottom
        bh = THIRD_H - 2*PAD    # box height

        WORD_W = bw - NUM_W - MARK_W

        # ── Header row ──────────────────────────────────────────────
        hdr_y = by + bh - HDR_H
        # Name cell (spans num + word cols)
        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.rect(bx, hdr_y, NUM_W + WORD_W, HDR_H, fill=1, stroke=1)
        # Mark header cell
        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.rect(bx + NUM_W + WORD_W, hdr_y, MARK_W, HDR_H, fill=1, stroke=1)

        # Name label + value
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.setFont("Helvetica", 8)
        c.drawString(bx + 4, hdr_y + HDR_H - 11, "Name")
        if pupil:
            name = pupil.get("first","")
            c.setFont("Helvetica-Bold", 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(bx + 30, hdr_y + HDR_H - 11, name)
        # Mark header text
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawCentredString(bx + NUM_W + WORD_W + MARK_W/2, hdr_y + HDR_H - 13, "Check")

        # ── Word rows ────────────────────────────────────────────────
        c.setFont("Helvetica", 9)
        for i in range(10):
            ry = hdr_y - (i + 1) * ROW_H
            # Number cell
            c.setFillColorRGB(1, 1, 1)
            c.rect(bx,               ry, NUM_W,  ROW_H, fill=1, stroke=1)
            # Word cell
            c.rect(bx + NUM_W,       ry, WORD_W, ROW_H, fill=1, stroke=1)
            # Mark cell
            c.rect(bx + NUM_W + WORD_W, ry, MARK_W, ROW_H, fill=1, stroke=1)
            # Row number
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawCentredString(bx + NUM_W/2, ry + ROW_H*0.3, str(i + 1))

    def draw_cut_lines():
        c.saveState()
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.6)
        c.setDash(5, 4)
        # Vertical centre
        c.line(HALF_W, 0, HALF_W, PH)
        # Horizontal thirds
        c.line(0, THIRD_H,     PW, THIRD_H)
        c.line(0, THIRD_H * 2, PW, THIRD_H * 2)
        c.restoreState()

    # Sort pupils
    sorted_pupils = list(pupils)

    # 6 per page (2 wide × 3 tall)
    for page_start in range(0, len(sorted_pupils), 6):
        batch = sorted_pupils[page_start:page_start+6]
        while len(batch) < 6:
            batch.append(None)

        # Positions (bottom-left corners), top row first:
        positions = [
            (0,      THIRD_H * 2),   # row 1 left
            (HALF_W, THIRD_H * 2),   # row 1 right
            (0,      THIRD_H),       # row 2 left
            (HALF_W, THIRD_H),       # row 2 right
            (0,      0),             # row 3 left
            (HALF_W, 0),             # row 3 right
        ]
        for i in range(6):
            qx, qy = positions[i]
            draw_quadrant(qx, qy, None)

        draw_cut_lines()
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


# ── TT Check sheet ─────────────────────────────────────────────────────────

def build_tt_check_sheet(pupils, week_ref, seed=None, variant=None):
    """
    A4 landscape. Two A5-portrait halves side by side, cut down the middle.
    Each half: Name + Score/Time box at top, shaded TT label, 40 questions in 2x20 columns.
    variant is derived per-pupil from tt_mode ('x' → A, 'xd' → B).
    Pupils arrive pre-sorted — order preserved.
    """
    if seed:
        random.seed(seed)

    buf = io.BytesIO()
    PW, PH = landscape(A4)   # 841.9 x 595.3 pt
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    HALF   = PW / 2          # ~421 pt per child
    PAD    = 8                # inner padding pt
    BORDER = 6               # border inset from half edge

    def questions_for(tt_set, pupil_variant):
        """
        Returns list of (display_str, is_division) tuples.
        Variant A: multiplication only. Variant B: ~60% × / ~40% ÷.
        """
        qs = []
        for i in range(40):
            if tt_set == "All":
                t  = random.randint(2, 12)
                f  = random.randint(2, 12)
                if pupil_variant == "B" and random.random() < 0.4:
                    product = t * f
                    qs.append((f"{product}  ÷  {t}  =", True))
                else:
                    if random.random() < 0.5:
                        qs.append((f"{t}  ×  {f}  =", False))
                    else:
                        qs.append((f"{f}  ×  {t}  =", False))
            else:
                t = int(tt_set)
                f = random.randint(2, 12)
                if pupil_variant == "B" and random.random() < 0.4:
                    product = t * f
                    qs.append((f"{product}  ÷  {t}  =", True))
                else:
                    if random.random() < 0.5:
                        qs.append((f"{t}  ×  {f}  =", False))
                    else:
                        qs.append((f"{f}  ×  {t}  =", False))
        return qs

    def tt_label(tt_set, pupil_variant):
        suffix = "  (× and ÷)" if pupil_variant == "B" else "  ×"
        if tt_set == "All":
            return "2,3,4,5,6,7,8,9,10,11,12" + suffix
        return f"{tt_set}" + suffix

    def draw_half(col, pupil):
        x0 = col * HALF     # left edge of this half
        bx = x0 + BORDER
        bw = HALF - 2 * BORDER
        bh = PH - 2 * BORDER
        by = BORDER

        # Outer border box
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.setLineWidth(1)
        c.rect(bx, by, bw, bh, fill=0, stroke=1)

        tt           = pupil.get("tt_set", "All")
        tt_mode      = pupil.get("tt_mode", "x")
        pupil_variant = "B" if tt_mode == "xd" else "A"
        first   = pupil.get("first", "")
        last    = pupil.get("last", "")
        name    = f"{first} {last}".strip()
        cls_lbl = pupil.get("cls", "")

        # ── Header row: Name (left) + Score/Time box (right) ──────────
        HDR_H  = 46             # taller header
        hdr_y  = by + bh - HDR_H
        name_w = bw * 0.58

        # "Name" label + bold name
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawString(bx + PAD, hdr_y + HDR_H - 15, "Name")
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(bx + PAD + 32, hdr_y + HDR_H - 15, name)
        # Underline
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.5)
        c.line(bx + PAD + 30, hdr_y + HDR_H - 17,
               bx + name_w - 4, hdr_y + HDR_H - 17)

        # Class label
        if cls_lbl:
            c.setFont("Helvetica", 8.5)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(bx + PAD, hdr_y + 6, cls_lbl)

        # Score / Time box — label INSIDE the box
        stx = bx + name_w + 4
        stw = bw - name_w - PAD - 4
        sth = HDR_H - 8
        sty = hdr_y + 4
        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.setLineWidth(0.8)
        c.rect(stx, sty, stw, sth, fill=0, stroke=1)
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(stx + stw / 2, sty + sth - 11, "Score / Time")

        # ── TT label bar ───────────────────────────────────────────────
        BAR_H = 20
        bar_y = hdr_y - BAR_H
        c.setFillColorRGB(0.88, 0.88, 0.88)
        c.rect(bx, bar_y, bw, BAR_H, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(bx + bw / 2, bar_y + 5, tt_label(tt, pupil_variant))

        # ── Questions table ────────────────────────────────────────────
        Q_TOP    = bar_y
        Q_BOTTOM = by
        Q_H      = Q_TOP - Q_BOTTOM
        ROW_H    = Q_H / 20

        GAP   = 8            # gap between the two sub-tables
        sub_w = (bw - GAP) / 2
        NUM_W = 28           # question number column width
        ANS_W = 44           # answer box column width
        EQ_W  = sub_w - NUM_W - ANS_W

        Q_FONT   = 12
        NUM_FONT = 10
        qs = questions_for(tt, pupil_variant)

        c.setLineWidth(0.5)

        for qi, (eq_str, is_div) in enumerate(qs):
            sub = 0 if qi < 20 else 1
            row = qi if qi < 20 else qi - 20

            tx      = bx + sub * (sub_w + GAP)
            row_top = Q_TOP - row * ROW_H
            row_bot = row_top - ROW_H
            row_mid = row_bot + ROW_H * 0.30

            # Cell borders
            c.setStrokeColorRGB(0.3, 0.3, 0.3)
            c.rect(tx,                row_bot, NUM_W, ROW_H, fill=0, stroke=1)
            c.rect(tx + NUM_W,        row_bot, EQ_W,  ROW_H, fill=0, stroke=1)
            c.rect(tx + NUM_W + EQ_W, row_bot, ANS_W, ROW_H, fill=0, stroke=1)

            # Question number (right-aligned in number cell)
            c.setFont("Helvetica", NUM_FONT)
            c.setFillColorRGB(0, 0, 0)
            num_str = f"{qi+1}."
            nw = c.stringWidth(num_str, "Helvetica", NUM_FONT)
            c.drawString(tx + NUM_W - nw - 3, row_mid, num_str)

            # Equation — right-aligned so "=" sits flush against answer box
            c.setFont("Helvetica", Q_FONT)
            if is_div:
                c.setFillColorRGB(0.15, 0.35, 0.65)   # blue tint for division
            else:
                c.setFillColorRGB(0, 0, 0)
            eqw = c.stringWidth(eq_str, "Helvetica", Q_FONT)
            c.drawString(tx + NUM_W + EQ_W - eqw - 4, row_mid, eq_str)
            c.setFillColorRGB(0, 0, 0)

    for idx in range(0, len(pupils), 2):
        pair = pupils[idx:idx+2]

        for col, pupil in enumerate(pair):
            draw_half(col, pupil)

        # Dashed cut line
        c.saveState()
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.6)
        c.setDash(5, 4)
        c.line(HALF, PH - 2, HALF, 2)
        c.restoreState()

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


"""
WFA Home Learning PDF Builder
Generates duplex-ready A4 landscape PDFs for all children.
Each child gets 2 pages: front (maths + reading) and back (spelling).
Pages are ordered: child1_front, child1_back, child2_front, child2_back...
"""

import io
import re
import json
import os
import random
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe

import qrcode
from PIL import Image

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Constants ─────────────────────────────────────────────────────────────────

W, H = landscape(A4)        # 841.9 x 595.3 pt
M    = 10 * mm              # 28.35 pt — page margin
DIV  = 1 * mm               # 2.83 pt  — gap at column divider
COL_W = (W - 2*M - DIV) / 2  # 391.2 pt ≈ 138 mm — each column width
R_X  = M + COL_W + DIV     # 422.4 pt — right column x start
ICO  = 8 * mm               # icon diameter
ICO_GAP = 2 * mm            # gap between icon and question text
Q_W  = COL_W - ICO - ICO_GAP  # question text width in reading column

# Brand colours (R, G, B 0–1)
BLUE  = (23/255, 152/255, 211/255)
NAVY  = (26/255, 60/255, 110/255)
DGREY = (0.35, 0.35, 0.35)
MGREY = (0.6, 0.6, 0.6)
LGREY = (0.82, 0.82, 0.82)
BLACK = (0, 0, 0)
WHITE = (1, 1, 1)

TT_URL = 'https://play.ttrockstars.com/auth/school/student/81920'

# Register Sassoon if available
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
_SASSOON = os.path.join(_FONT_DIR, 'SassoonInfant.ttf')
if os.path.exists(_SASSOON):
    try:
        pdfmetrics.registerFont(TTFont('SassoonInfant', _SASSOON))
        BODY_FONT = 'SassoonInfant'
    except Exception:
        BODY_FONT = 'Helvetica'
else:
    BODY_FONT = 'Helvetica'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _week_label(week_ref):
    """'T5W5' → 'Term 5 Week 5'"""
    m = re.match(r'T(\d+)W(\d+)', week_ref)
    return f"Term {m.group(1)} Week {m.group(2)}" if m else week_ref


def _tt_label(tt_set):
    """'9' → '9', 'All' → 'all'"""
    if str(tt_set).lower() == 'all':
        return 'all'
    return str(tt_set)


def _set_fill(c, rgb):
    c.setFillColorRGB(*rgb)


def _set_stroke(c, rgb):
    c.setStrokeColorRGB(*rgb)


def _hrule(c, x, y, w, rgb=LGREY, lw=0.5):
    _set_stroke(c, rgb)
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)


# ── Grid generator ────────────────────────────────────────────────────────────

def generate_hl_grid(elements, grid_size=10, px=280):
    """
    Render a grid with the given elements.
    Returns PNG bytes.
    elements: list of dicts with 'type' and type-specific keys.
    """
    dpi = 150
    fig_in = px / dpi
    fig, ax = plt.subplots(figsize=(fig_in, fig_in), dpi=dpi)

    ax.set_xlim(0, grid_size)
    ax.set_ylim(0, grid_size)
    ax.set_xticks(range(grid_size + 1))
    ax.set_yticks(range(grid_size + 1))
    ax.grid(True, linewidth=0.4, color='#aaaaaa', zorder=0)
    ax.set_aspect('equal')
    ax.tick_params(labelsize=6, length=2, pad=1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    for elem in (elements or []):
        etype = elem.get('type', '')

        if etype == 'point':
            ax.plot(elem['x'], elem['y'], 'k.', markersize=5, zorder=5)
            lbl = elem.get('label', '')
            if lbl:
                ax.annotate(lbl, (elem['x'], elem['y']),
                            xytext=(3, 3), textcoords='offset points',
                            fontsize=7, fontweight='bold')

        elif etype == 'arrow':
            ax.annotate('', xy=(elem['x2'], elem['y2']),
                        xytext=(elem['x1'], elem['y1']),
                        arrowprops=dict(arrowstyle='->', color='#1A3C6E', lw=1.4),
                        zorder=5)
            for key, (ex, ey) in [('label_start', (elem['x1'], elem['y1'])),
                                   ('label_end', (elem['x2'], elem['y2']))]:
                lbl = elem.get(key, '')
                if lbl:
                    ax.annotate(lbl, (ex, ey), xytext=(3, 3),
                                textcoords='offset points', fontsize=7, fontweight='bold')

        elif etype in ('polygon', 'triangle'):
            pts = elem['points']
            poly = plt.Polygon(
                pts,
                closed=True,
                fill=elem.get('fill', True),
                facecolor=elem.get('facecolor', '#cce4f5'),
                edgecolor='#1A3C6E',
                linewidth=1.5,
                zorder=4
            )
            ax.add_patch(poly)
            # label vertices
            for i, (px_, py_) in enumerate(pts):
                lbl = elem.get('labels', [''] * len(pts))
                if i < len(lbl) and lbl[i]:
                    ax.annotate(lbl[i], (px_, py_), xytext=(3, 3),
                                textcoords='offset points', fontsize=7, fontweight='bold')

        elif etype == 'star':
            ax.plot(elem['x'], elem['y'], 'k*', markersize=9, zorder=5)
            lbl = elem.get('label', '')
            if lbl:
                ax.annotate(lbl, (elem['x'], elem['y']),
                            xytext=(3, 3), textcoords='offset points',
                            fontsize=7, fontweight='bold')

        elif etype == 'mirror_v':
            ax.axvline(x=elem['x'], color='#1A3C6E', linewidth=1.5,
                       linestyle='--', zorder=3)

        elif etype == 'mirror_h':
            ax.axhline(y=elem['y'], color='#1A3C6E', linewidth=1.5,
                       linestyle='--', zorder=3)

        elif etype == 'rect':
            x0, y0 = elem['x'], elem['y']
            w_, h_ = elem['w'], elem['h']
            rect = plt.Rectangle(
                (x0, y0), w_, h_,
                fill=elem.get('fill', False),
                facecolor=elem.get('facecolor', '#cce4f5'),
                edgecolor='#1A3C6E',
                linewidth=1.5,
                zorder=4
            )
            ax.add_patch(rect)
            for key, (ex, ey) in [('label_tl', (x0, y0+h_)),
                                   ('label_tr', (x0+w_, y0+h_)),
                                   ('label_br', (x0+w_, y0)),
                                   ('label_bl', (x0, y0))]:
                lbl = elem.get(key, '')
                if lbl:
                    ax.annotate(lbl, (ex, ey), xytext=(2, 2),
                                textcoords='offset points', fontsize=7, fontweight='bold')

        elif etype == 'label':
            ax.text(elem['x'], elem['y'], elem['text'],
                    fontsize=elem.get('fontsize', 7), ha='center', va='center')

    plt.tight_layout(pad=0.2)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── QR code ───────────────────────────────────────────────────────────────────

def generate_qr_png(url):
    """Return PNG bytes for a QR code linking to url."""
    qr = qrcode.QRCode(version=1, box_size=4, border=2,
                        error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()


# ── Icon drawing ──────────────────────────────────────────────────────────────

def _draw_icon(c, cx, cy, r, icon_type):
    """
    Draw an icon circle at centre (cx, cy) with radius r.
    icon_type: 'retrieval' | 'vocabulary' | 'inference'
    """
    _set_stroke(c, NAVY)
    _set_fill(c, WHITE)
    c.setLineWidth(0.8)
    c.circle(cx, cy, r, fill=1, stroke=1)

    _set_fill(c, NAVY)

    if icon_type == 'retrieval':
        # Magnifying glass: small circle + handle line
        ir = r * 0.38
        icx = cx - r * 0.08
        icy = cy + r * 0.08
        c.setLineWidth(1.0)
        _set_stroke(c, NAVY)
        _set_fill(c, WHITE)
        c.circle(icx, icy, ir, fill=1, stroke=1)
        _set_stroke(c, NAVY)
        c.setLineWidth(1.2)
        c.line(icx + ir * 0.65, icy - ir * 0.65,
               cx + r * 0.5, cy - r * 0.5)

    elif icon_type == 'vocabulary':
        # "ABC" centred
        fs = r * 0.75
        c.setFont('Helvetica-Bold', fs)
        _set_fill(c, NAVY)
        c.drawCentredString(cx, cy - fs * 0.35, 'ABC')

    elif icon_type == 'inference':
        # Thought cloud: main ellipse + two small circles descending
        _set_stroke(c, NAVY)
        _set_fill(c, WHITE)
        c.setLineWidth(0.7)
        # Main cloud body (ellipse)
        c.ellipse(cx - r*0.42, cy - r*0.05, cx + r*0.42, cy + r*0.45,
                  fill=1, stroke=1)
        # Thought dots descending
        c.circle(cx - r*0.15, cy - r*0.2, r*0.1, fill=1, stroke=1)
        c.circle(cx - r*0.05, cy - r*0.42, r*0.07, fill=1, stroke=1)


# ── Front page: left column (maths) ──────────────────────────────────────────

def _draw_maths_col(c, pupil, cfg, week_ref, grid_png, qr_png):
    """Draw left (maths) column. x=M, usable width=COL_W."""
    x = M
    w = COL_W
    top = H - M
    cy = top

    # ── Header ──────────────────────────────────────────────────────────────
    term_label = _week_label(week_ref)
    first = pupil.get('first', '')
    header = f"{term_label} \u2013 Home Learning \u2013 {first}"
    fs_hdr = 10
    c.setFont('Helvetica-Bold', fs_hdr)
    _set_fill(c, BLACK)
    cy -= fs_hdr * 0.85
    c.drawCentredString(x + w/2, cy, header)
    cy -= fs_hdr * 0.15 + 1.5*mm

    _hrule(c, x, cy, w, NAVY, 0.6)
    cy -= 1.5*mm

    # ── Subheader ────────────────────────────────────────────────────────────
    fs_sub = 9.5
    c.setFont('Helvetica-Bold', fs_sub)
    _set_fill(c, BLACK)
    cy -= fs_sub * 0.85
    c.drawCentredString(x + w/2, cy, 'Being a Mathematician')
    cy -= fs_sub * 0.15 + 1*mm

    _hrule(c, x, cy, w, LGREY, 0.4)
    cy -= 2*mm

    # ── Instruction ──────────────────────────────────────────────────────────
    instruction = cfg.get('maths_instruction',
                          'Use the grid to answer questions 1, 2 and 3. '
                          'For questions 4 and 5, use the space below.')
    fs_inst = 7.5
    c.setFont('Helvetica-Oblique', fs_inst)
    _set_fill(c, DGREY)
    inst_lines = simpleSplit(instruction, 'Helvetica-Oblique', fs_inst, w)
    for line in inst_lines:
        cy -= fs_inst * 0.85
        c.drawString(x, cy, line)
        cy -= fs_inst * 0.15
    cy -= 2*mm

    # ── Grid image ───────────────────────────────────────────────────────────
    GRID_SIZE = 185  # fixed grid square in points (≈65mm)
    if grid_png:
        grid_img = ImageReader(io.BytesIO(grid_png))
        c.drawImage(grid_img, x, cy - GRID_SIZE, GRID_SIZE, GRID_SIZE,
                    preserveAspectRatio=True, mask='auto')
    cy -= GRID_SIZE + 2*mm

    # ── Questions ────────────────────────────────────────────────────────────
    questions = cfg.get('questions', [])
    # Reserve space for TT bar at bottom
    TT_BAR_H = 11*mm
    q_bottom = M + TT_BAR_H + 1*mm
    q_avail = cy - q_bottom
    q_space_per = q_avail / max(len(questions), 1) if questions else 0

    fs_qh = 8.5   # question heading font size
    fs_qt = 8.0   # question text font size

    for qi, q in enumerate(questions):
        qx = x
        heading = q.get('heading', '')
        text    = q.get('text', '')
        atype   = q.get('answer_type', 'lines')
        alines  = q.get('answer_lines', 0)

        # Heading
        c.setFont('Helvetica-Bold', fs_qh)
        _set_fill(c, BLACK)
        cy -= fs_qh * 0.85
        c.drawString(qx, cy, f'{qi+1}.  {heading}')
        cy -= fs_qh * 0.15 + 1*mm

        # Question text
        c.setFont('Helvetica', fs_qt)
        _set_fill(c, BLACK)
        qt_lines = simpleSplit(text, 'Helvetica', fs_qt, w - 6*mm)
        for line in qt_lines:
            cy -= fs_qt * 0.85
            c.drawString(qx + 6*mm, cy, line)
            cy -= fs_qt * 0.15
        cy -= 1*mm

        # Answer area
        if atype == 'truefalse':
            c.setFont('Helvetica-Bold', fs_qt)
            _set_fill(c, BLACK)
            cy -= fs_qt * 0.85
            c.drawString(qx + 6*mm, cy, 'TRUE          FALSE')
            cy -= fs_qt * 0.15 + 1*mm

        elif atype == 'column_method':
            # Draw two column-method grids side by side (for parts a and b)
            BOX  = 6.2 * mm   # cell size
            COLS = ['Th', 'H', 'T', 'O']
            ROWS = 3          # top number, bottom number, answer
            G_W  = BOX * len(COLS)
            G_H  = BOX * ROWS
            HDR  = 4.8 * mm
            GAP  = 8 * mm
            cy -= HDR + G_H + 2*mm
            for gi in range(2):
                gx = qx + gi * (G_W + GAP)
                # Column headers
                c.setFont('Helvetica-Bold', 6.5)
                _set_fill(c, DGREY)
                for ci, lbl in enumerate(COLS):
                    c.drawCentredString(gx + ci*BOX + BOX/2, cy + G_H + HDR*0.4, lbl)
                # Grid cells
                c.setStrokeColorRGB(0.55, 0.55, 0.55)
                c.setLineWidth(0.4)
                for ri in range(ROWS):
                    ry = cy + (ROWS - 1 - ri) * BOX
                    for ci in range(len(COLS)):
                        c.rect(gx + ci*BOX, ry, BOX, BOX, fill=0, stroke=1)
                # Answer line (heavy) above bottom row
                c.setStrokeColorRGB(0.2, 0.2, 0.2)
                c.setLineWidth(0.8)
                c.line(gx, cy + BOX, gx + G_W, cy + BOX)

        elif atype == 'lines' and alines > 0:
            for _ in range(alines):
                cy -= 7*mm
                _hrule(c, qx + 2*mm, cy, w - 2*mm, LGREY, 0.5)

        cy -= 1.5*mm

    # ── TT bar ───────────────────────────────────────────────────────────────
    bar_y = M
    bar_h = TT_BAR_H

    _hrule(c, x, bar_y + bar_h, w, LGREY, 0.4)

    # QR code
    QR_SIZE = bar_h - 1*mm
    if qr_png:
        qr_img = ImageReader(io.BytesIO(qr_png))
        c.drawImage(qr_img, x, bar_y + 0.5*mm, QR_SIZE, QR_SIZE,
                    preserveAspectRatio=True, mask='auto')

    # TT text
    tt_set = pupil.get('tt_set', 'all')
    tt_lbl = _tt_label(tt_set)
    tt_text = f'This week, please practise  {tt_lbl}  times table(s).'
    tt_x = x + QR_SIZE + 3*mm
    c.setFont('Helvetica-Bold', 9)
    _set_fill(c, NAVY)
    c.drawString(tt_x, bar_y + bar_h/2 - 4.5, tt_text)


# ── Front page: right column (reading) ───────────────────────────────────────

def _draw_reading_col(c, cfg):
    """Draw right (reading) column. x=R_X, usable width=COL_W."""
    x = R_X
    w = COL_W
    top = H - M
    cy = top

    # ── Vertical divider ─────────────────────────────────────────────────────
    _set_stroke(c, LGREY)
    c.setLineWidth(0.6)
    c.line(R_X - DIV/2, H - M, R_X - DIV/2, M)

    # ── Header ───────────────────────────────────────────────────────────────
    fs_hdr = 9.5
    c.setFont('Helvetica-Bold', fs_hdr)
    _set_fill(c, BLACK)
    cy -= fs_hdr * 0.85
    c.drawCentredString(x + w/2, cy, 'Being a Reader')
    cy -= fs_hdr * 0.15 + 1.5*mm

    _hrule(c, x, cy, w, NAVY, 0.6)
    cy -= 2*mm

    # ── Passage ───────────────────────────────────────────────────────────────
    passage = cfg.get('passage', '')
    fs_p = 10.5
    leading = fs_p * 1.28
    c.setFont('Helvetica-Oblique', fs_p)
    _set_fill(c, BLACK)
    p_lines = simpleSplit(passage, 'Helvetica-Oblique', fs_p, w)
    for line in p_lines:
        cy -= fs_p * 0.85
        c.drawString(x, cy, line)
        cy -= fs_p * 0.15 + (leading - fs_p)
    cy -= 2*mm

    # ── Reading questions ────────────────────────────────────────────────────
    rqs = cfg.get('reading_questions', [])
    ICON_TYPES = {'retrieval': 'retrieval', 'vocabulary': 'vocabulary',
                  'inference': 'inference'}

    for rq in rqs:
        qtype  = rq.get('type', 'retrieval')
        qtext  = rq.get('text', '')
        qlines = rq.get('lines', 2)
        fs_q   = 8.5

        # Question text (beside icon)
        q_lines_split = simpleSplit(qtext, 'Helvetica-Bold', fs_q, Q_W)
        q_text_h = len(q_lines_split) * fs_q * 1.25
        row_h = max(ICO, q_text_h)

        q_top = cy
        # Icon: centred vertically against question text height
        ico_r = ICO / 2
        ico_cx = x + ico_r
        ico_cy = q_top - row_h/2
        _draw_icon(c, ico_cx, ico_cy, ico_r, ICON_TYPES.get(qtype, 'retrieval'))

        # Question text
        c.setFont('Helvetica-Bold', fs_q)
        _set_fill(c, BLACK)
        tx = x + ICO + ICO_GAP
        for li, line in enumerate(q_lines_split):
            bl = q_top - li * fs_q * 1.25 - fs_q * 0.85
            c.drawString(tx, bl, line)

        cy = q_top - row_h - 1*mm

        # Answer lines
        for _ in range(qlines):
            cy -= 7*mm
            _hrule(c, x, cy, w, LGREY, 0.5)
        cy -= 2*mm


# ── Back page: spelling ───────────────────────────────────────────────────────

def _draw_spelling_back(c, pupil, rule_title, rule_words, key_words):
    """
    Draw the personalised spelling back page.
    Full A4 landscape, full width.
    """
    x = M
    w = W - 2*M
    cy = H - M

    # ── Header line ──────────────────────────────────────────────────────────
    c.setFont('Helvetica-Bold', 9)
    _set_fill(c, BLACK)
    cy -= 9 * 0.85
    c.drawString(x, cy, 'Personal Key Spellings and Weekly Spelling Rule Words')
    ss_user = pupil.get('ss_user', '')
    ss_pass = pupil.get('ss_pass', '')
    if ss_user or ss_pass:
        c.setFont('Helvetica', 8.5)
        _set_fill(c, DGREY)
        c.drawRightString(x + w, cy, f'Spelling Shed \u2013 {ss_user} / {ss_pass}')
    cy -= 9 * 0.15 + 1*mm

    _hrule(c, x, cy, w, NAVY, 0.6)
    cy -= 3*mm

    # ── Instruction text ─────────────────────────────────────────────────────
    instruction = (
        f"The first 5 words below are your Key Spellings. "
        f"This week\u2019s spelling rule \u2013 {rule_title}. "
        f"Practise spelling these words. Write each word within a sentence "
        f"in the space below. These words will be checked in your paired spelling bee."
    )
    fs_inst = 8.5
    c.setFont('Helvetica', fs_inst)
    _set_fill(c, DGREY)
    inst_lines = simpleSplit(instruction, 'Helvetica', fs_inst, w)
    for line in inst_lines:
        cy -= fs_inst * 0.85
        c.drawString(x, cy, line)
        cy -= fs_inst * 0.15
    cy -= 3*mm

    _hrule(c, x, cy, w, LGREY, 0.4)
    cy -= 2*mm

    # ── Table layout ─────────────────────────────────────────────────────────
    GLUE_H  = 20 * mm          # 20mm gluing strip at bottom
    TABLE_BOTTOM = M + GLUE_H + 4*mm
    table_h = cy - TABLE_BOTTOM
    words = list(key_words[:5]) + list(rule_words[:5])
    n = len(words)
    row_h = table_h / n if n > 0 else 0

    # Column split: word col ~65mm, line col = rest
    WORD_COL_W = 65 * mm
    LINE_COL_W = w - WORD_COL_W
    WORD_COL_X = x
    LINE_COL_X = x + WORD_COL_W
    table_top = cy

    # Outer border
    _set_stroke(c, MGREY)
    c.setLineWidth(0.6)
    c.rect(x, TABLE_BOTTOM, w, table_h, fill=0, stroke=1)

    # Vertical divider between word and line columns
    c.setLineWidth(0.5)
    c.line(LINE_COL_X, TABLE_BOTTOM, LINE_COL_X, table_top)

    # Each word row
    for i, word in enumerate(words):
        row_top = table_top - i * row_h
        row_bot = row_top - row_h

        # Horizontal row divider in word column (light, between rows)
        if i > 0:
            _set_stroke(c, LGREY)
            c.setLineWidth(0.3)
            c.line(WORD_COL_X, row_top, LINE_COL_X, row_top)

        # Word number + word
        is_key = i < 5
        fs_w = 9.5
        c.setFont('Helvetica-Bold' if is_key else 'Helvetica', fs_w)
        _set_fill(c, NAVY if is_key else DGREY)
        word_bl = row_top - row_h/2 - fs_w * 0.35
        c.drawString(WORD_COL_X + 3*mm, word_bl, f'{i+1}.  {word}')

        # Two writing lines at 8mm apart in the line column
        # Centre the pair vertically within the row
        LINE_SEP = 8 * mm   # 8mm between lines (school book ruling)
        pair_h = LINE_SEP
        line1_y = row_top - (row_h - pair_h) / 2 - 1*mm
        line2_y = line1_y - LINE_SEP

        # Ensure lines stay within the row
        if line1_y > row_top - 1*mm:
            line1_y = row_top - 2*mm
        if line2_y < row_bot + 1*mm:
            line2_y = row_bot + 1*mm

        _set_stroke(c, MGREY)
        c.setLineWidth(0.5)
        c.line(LINE_COL_X + 2*mm, line1_y, x + w - 2*mm, line1_y)
        c.line(LINE_COL_X + 2*mm, line2_y, x + w - 2*mm, line2_y)

    # ── Glue strip ───────────────────────────────────────────────────────────
    GLUE_TOP = M + GLUE_H
    _set_stroke(c, LGREY)
    c.setLineWidth(0.3)
    c.setDash(3, 3)
    c.line(x, GLUE_TOP, x + w, GLUE_TOP)
    c.setDash()

    # Faint repeated "glue here" text
    c.setFont('Helvetica', 6.5)
    _set_fill(c, (0.78, 0.78, 0.78))
    glue_y = M + GLUE_H/2 - 3
    repeat_x = x
    while repeat_x < x + w - 20*mm:
        c.drawString(repeat_x, glue_y, 'glue here')
        repeat_x += 25*mm


# ── Master builder ────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# HOME LEARNING PDF
# ══════════════════════════════════════════════════════════════════════════════

import io as _io

_HL_QR_URL  = "https://play.ttrockstars.com/auth/school/student/81920"
_HL_GRID_PT = 175

def _hl_grid_png(elements, grid_size=10):
    """Return matplotlib grid PNG bytes, or None if no elements / matplotlib missing."""
    if not elements:
        return None
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        fig, ax = plt.subplots(figsize=(4, 4), dpi=150)
        ax.set_xlim(0, grid_size)
        ax.set_ylim(0, grid_size)
        ax.set_xticks(range(grid_size + 1))
        ax.set_yticks(range(grid_size + 1))
        ax.grid(True, color='#cccccc', linewidth=0.5)
        ax.tick_params(labelsize=7)
        ax.set_aspect('equal')

        for el in elements:
            t   = el.get('type', '')
            col = el.get('color', '#1A3C6E')

            if t == 'point':
                ax.plot(el['x'], el['y'], 'o', color=col, markersize=5, zorder=5)
                if el.get('label'):
                    ax.annotate(f" {el['label']}", (el['x'], el['y']),
                                fontsize=7, color=col, va='bottom')
            elif t == 'arrow':
                ax.annotate('', xy=(el['x2'], el['y2']),
                            xytext=(el['x1'], el['y1']),
                            arrowprops=dict(arrowstyle='->', color=col, lw=1.5))
                if el.get('label'):
                    mx = (el['x1'] + el['x2']) / 2
                    my = (el['y1'] + el['y2']) / 2
                    ax.annotate(el['label'], (mx, my), fontsize=6.5, color=col,
                                ha='center', va='bottom')
            elif t == 'triangle':
                verts = el['vertices']
                tri = plt.Polygon(verts, closed=True,
                                  facecolor=el.get('fill', 'lightblue'),
                                  edgecolor=col, linewidth=1.5, alpha=0.7)
                ax.add_patch(tri)
                if el.get('label'):
                    cx = sum(v[0] for v in verts) / 3
                    cy_c = sum(v[1] for v in verts) / 3
                    ax.annotate(el['label'], (cx, cy_c), fontsize=7, ha='center')
            elif t == 'rectangle':
                x1, y1, x2, y2 = el['x1'], el['y1'], el['x2'], el['y2']
                rect = mpatches.Rectangle(
                    (min(x1, x2), min(y1, y2)), abs(x2-x1), abs(y2-y1),
                    linewidth=1.5, edgecolor=col,
                    facecolor=el.get('fill', 'none'), alpha=0.5)
                ax.add_patch(rect)
                for vl in el.get('vertex_labels', []):
                    ax.annotate(vl['label'], (vl['x'], vl['y']),
                                fontsize=6.5, color=col, ha='center', va='bottom')
            elif t == 'star':
                ax.plot(el['x'], el['y'], '*', color=col, markersize=12, zorder=5)
                if el.get('label'):
                    ax.annotate(f" {el['label']}", (el['x'], el['y']),
                                fontsize=7, color=col, va='bottom')
            elif t == 'polygon':
                poly = plt.Polygon(el['vertices'], closed=True,
                                   facecolor=el.get('fill', 'none'),
                                   edgecolor=col, linewidth=1.5)
                ax.add_patch(poly)
            elif t == 'mirror_v':
                ax.axvline(x=el['x'], color=col, linewidth=1.5, linestyle='--')
            elif t == 'mirror_h':
                ax.axhline(y=el['y'], color=col, linewidth=1.5, linestyle='--')
            elif t == 'label':
                ax.annotate(el.get('text', ''), (el['x'], el['y']),
                            fontsize=7, color=col, ha='center', va='center')

        plt.tight_layout(pad=0.1)
        buf = _io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None



def _hl_qr_png(url=_HL_QR_URL):
    """Return QR code PNG bytes, or None if qrcode not installed."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=4, border=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = _io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.read()
    except Exception:
        return None



def _sort_pupils_for_hl(pupils):
    """Sort by class (IM first) then table number (empty last), then name."""
    def key(p):
        cls_order = 0 if p.get('cls') == 'IM' else 1
        tbl = p.get('table', '')
        try:
            tbl_num = int(tbl) if tbl else 999
        except ValueError:
            tbl_num = 999
        return (cls_order, tbl_num, p.get('first', ''))
    return sorted(pupils, key=key)



def get_hl_key_words_map(pupils):
    """Build {pupil_id: [word1..word5]} from each pupil's active words."""
    from word_bank import get_active_words as _gaw
    result = {}
    for p in pupils:
        mastered = set(p.get('mastered', []))
        result[p['id']] = _gaw(p.get('word_pos', 0), mastered, count=5)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# HOME LEARNING PDF
# ══════════════════════════════════════════════════════════════════════════════

import io as _io
import os as _os_hl

_HL_QR_URL   = "https://play.ttrockstars.com/auth/school/student/81920"
_HL_GRID_PT  = 180   # pt — grid image square size on page

# ── XCCW cursive font registration ────────────────────────────────────────────
_FONT_DIR_HL  = _os_hl.path.join(_os_hl.path.dirname(_os_hl.path.abspath(__file__)), 'fonts')
_XCCW_REGISTERED = False
_TOP_EXIT = set('orvwx')

def _ensure_xccw():
    global _XCCW_REGISTERED
    if _XCCW_REGISTERED:
        return
    from reportlab.pdfbase.ttfonts import TTFont
    for name in ('XCCW_Joined_4a', 'XCCW_Joined_4b'):
        path = _os_hl.path.join(_FONT_DIR_HL, f'{name}.ttf')
        if _os_hl.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    _XCCW_REGISTERED = True

def _xccw_font(ch, prev):
    """Return XCCW font variant based on previous character."""
    if prev and prev in _TOP_EXIT:
        return 'XCCW_Joined_4b'
    return 'XCCW_Joined_4a'

def _xccw_width(text, size):
    """Measure width of text rendered char-by-char in XCCW."""
    _ensure_xccw()
    w = 0
    prev = None
    for ch in text:
        font = _xccw_font(ch, prev)
        try:
            w += pdfmetrics.stringWidth(ch, font, size)
        except Exception:
            w += pdfmetrics.stringWidth(ch, 'Helvetica', size)
        prev = ch if ch.strip() else None
    return w

def _draw_xccw(c, x, y, text, size):
    """Draw text using XCCW cursive font with correct 4a/4b join variants."""
    _ensure_xccw()
    prev = None
    for ch in text:
        font = _xccw_font(ch, prev)
        try:
            c.setFont(font, size)
        except Exception:
            c.setFont('Helvetica', size)
        c.drawString(x, y, ch)
        try:
            x += pdfmetrics.stringWidth(ch, font, size)
        except Exception:
            x += pdfmetrics.stringWidth(ch, 'Helvetica', size)
        prev = ch if ch.strip() else None


_ICON_DIR = _os_hl.path.join(_os_hl.path.dirname(_os_hl.path.abspath(__file__)), 'icons')
_ICON_FILES = {
    'retrieval':  'icon_retrieval.png',
    'vocabulary': 'icon_vocabulary.png',
    'inference':  'icon_inference.png',
}


def _hl_icon(c, cx, cy, icon_type, size):
    """Draw a reading question icon centred at (cx, cy) using PNG asset."""
    from reportlab.lib.utils import ImageReader
    fname = _ICON_FILES.get(icon_type, 'icon_retrieval.png')
    path  = _os_hl.path.join(_ICON_DIR, fname)
    if _os_hl.path.exists(path):
        img = ImageReader(path)
        c.drawImage(img, cx - size / 2, cy - size / 2, size, size,
                    preserveAspectRatio=True, mask='auto')
    else:
        # Fallback: plain grey circle if asset missing
        c.setFillColorRGB(0.87, 0.87, 0.87)
        c.setStrokeColorRGB(0.22, 0.22, 0.22)
        c.setLineWidth(0.8)
        c.circle(cx, cy, size / 2, fill=1, stroke=1)


def _hl_maths_col(c, x, top_y, col_w, col_h, pupil, cfg, week_ref, grid_png, qr_png):
    """Draw the maths (left) column. top_y is the top of the content table."""
    from reportlab.lib.utils import simpleSplit, ImageReader

    PAD      = 3 * mm
    cx_      = x + PAD
    cw_      = col_w - 2 * PAD
    cy       = top_y - PAD
    TT_BAR_H = 14 * mm

    # Section header
    fs_hdr = 10
    c.setFont('Helvetica-Bold', fs_hdr)
    c.setFillColorRGB(*BLACK)
    cy -= fs_hdr * 0.85
    c.drawCentredString(x + col_w / 2, cy, 'Being a Mathematician')
    cy -= fs_hdr * 0.15 + 1.5 * mm

    c.setStrokeColorRGB(0.55, 0.55, 0.55)
    c.setLineWidth(0.4)
    c.line(cx_, cy, x + col_w - PAD, cy)
    cy -= 3 * mm

    # Grid instruction
    if grid_png and (cfg.get('maths_instruction') or cfg.get('grid_instruction')):
        instr_txt = cfg.get('maths_instruction') or cfg.get('grid_instruction', '')
        c.setFont('Helvetica-Oblique', 7.5)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        for ln in simpleSplit(instr_txt, 'Helvetica-Oblique', 7.5, cw_):
            c.drawString(cx_, cy - 7.5 * 0.85, ln)
            cy -= 7.5 * 1.3
        cy -= 1 * mm

    # Grid image
    if grid_png:
        img_r = ImageReader(_io.BytesIO(grid_png))
        img_x = x + (col_w - _HL_GRID_PT) / 2
        img_y = cy - _HL_GRID_PT
        c.drawImage(img_r, img_x, img_y, _HL_GRID_PT, _HL_GRID_PT,
                    preserveAspectRatio=True)
        cy -= _HL_GRID_PT + 3 * mm

    # Questions
    questions = cfg.get('questions', [])
    for i, q in enumerate(questions):
        heading = q.get('heading', f'Q{i+1}')
        text    = q.get('text', '')
        n_ans   = q.get('answer_lines', 0)

        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColorRGB(*BLACK)
        c.drawString(cx_, cy - 8.5 * 0.85, f"{i+1}.  {heading}")
        cy -= 8.5 * 1.35

        if text:
            c.setFont('Helvetica', 8)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            for ql in simpleSplit(text, 'Helvetica', 8, cw_ - 4 * mm):
                c.drawString(cx_ + 4 * mm, cy - 8 * 0.85, ql)
                cy -= 8 * 1.35
            cy -= 0.5 * mm

        if n_ans > 0:
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.setLineWidth(0.45)
            for _ in range(n_ans):
                c.line(cx_, cy - 1 * mm, x + col_w - PAD, cy - 1 * mm)
                cy -= 7 * mm
            cy -= 1 * mm

        cy -= 2 * mm

    # TT bar pinned to column bottom
    bar_y = top_y - col_h
    c.setFillColorRGB(0.93, 0.93, 0.93)
    c.rect(x, bar_y, col_w, TT_BAR_H, fill=1, stroke=0)

    QR_SZ = 12 * mm
    if qr_png:
        qr_r = ImageReader(_io.BytesIO(qr_png))
        c.drawImage(qr_r, x + 2 * mm, bar_y + (TT_BAR_H - QR_SZ) / 2,
                    QR_SZ, QR_SZ, preserveAspectRatio=True)

    tt_set   = pupil.get('tt_set', 'All')
    txt_x    = x + (QR_SZ + 4 * mm if qr_png else 3 * mm)
    baseline = bar_y + TT_BAR_H / 2 - 5

    # "This week, please practise  " small
    pre = "This week, please practise  "
    c.setFont('Helvetica', 9)
    c.setFillColorRGB(*NAVY)
    c.drawString(txt_x, baseline, pre)
    pre_w = c.stringWidth(pre, 'Helvetica', 9)

    # TT value — large and bold
    c.setFont('Helvetica-Bold', 15)
    c.drawString(txt_x + pre_w, baseline, str(tt_set))
    tt_w = c.stringWidth(str(tt_set), 'Helvetica-Bold', 15)

    # " times table(s)." small again
    c.setFont('Helvetica', 9)
    c.drawString(txt_x + pre_w + tt_w + 2, baseline, " times table(s).")


def _hl_reading_col(c, x, top_y, col_w, col_h, cfg):
    """Draw the reading (right) column. top_y is the top of the content table."""
    from reportlab.lib.utils import simpleSplit

    PAD     = 3 * mm
    cx_     = x + PAD
    cw_     = col_w - 2 * PAD
    cy      = top_y - PAD
    ICO_SZ  = 9 * mm
    ICO_GAP = 2.5 * mm
    Q_W     = cw_ - ICO_SZ - ICO_GAP
    ANS_GAP = 7 * mm

    # Section header
    fs_hdr = 10
    c.setFont('Helvetica-Bold', fs_hdr)
    c.setFillColorRGB(*BLACK)
    cy -= fs_hdr * 0.85
    c.drawCentredString(x + col_w / 2, cy, 'Being a Reader')
    cy -= fs_hdr * 0.15 + 1.5 * mm

    c.setStrokeColorRGB(0.55, 0.55, 0.55)
    c.setLineWidth(0.4)
    c.line(cx_, cy, x + col_w - PAD, cy)
    cy -= 3 * mm

    # Passage
    passage = cfg.get('passage', '')
    if passage:
        c.setFont('Helvetica-Oblique', 9)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        for pl in simpleSplit(passage, 'Helvetica-Oblique', 9, cw_):
            c.drawString(cx_, cy - 9 * 0.85, pl)
            cy -= 9 * 1.28
        cy -= 3 * mm

    # Reading questions
    for q in cfg.get('reading_questions', []):
        q_type  = q.get('type', 'retrieval')
        q_text  = q.get('text', '')
        n_lines = q.get('lines', 2)

        q_lines   = simpleSplit(q_text, 'Helvetica-Bold', 8.5, Q_W)
        q_block_h = len(q_lines) * 8.5 * 1.3

        ico_cx = cx_ + ICO_SZ / 2
        ico_cy = cy - q_block_h / 2
        _hl_icon(c, ico_cx, ico_cy, q_type, ICO_SZ)

        q_x = cx_ + ICO_SZ + ICO_GAP
        q_y = cy
        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColorRGB(*BLACK)
        for ql in q_lines:
            c.drawString(q_x, q_y - 8.5 * 0.85, ql)
            q_y -= 8.5 * 1.3

        cy = q_y - 2 * mm

        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.setLineWidth(0.45)
        for _ in range(n_lines):
            c.line(cx_, cy - 1 * mm, x + col_w - PAD, cy - 1 * mm)
            cy -= ANS_GAP
        cy -= 2.5 * mm


def _hl_spelling_page(c, pupil, rule_title, rule_words, key_words, week_ref,
                      rule_explanation=''):
    """Draw the spelling back page. Caller calls c.showPage() afterwards."""
    from reportlab.lib.utils import simpleSplit

    W, H   = landscape(A4)
    M      = 10 * mm
    UW     = W - 2 * M
    WORD_W = 62 * mm
    LINE_X = M + WORD_W
    GLUE_H = 18 * mm

    _ensure_xccw()
    SPELL_FS = 14

    cy = H - M

    # Header
    c.setFont('Helvetica-Bold', 9)
    c.setFillColorRGB(*NAVY)
    c.drawString(M, cy - 9 * 0.85,
                 'Personal Key Spellings and Weekly Spelling Rule Words')
    ss_u = pupil.get('ss_user', '')
    ss_p = pupil.get('ss_pass', '')
    if ss_u or ss_p:
        c.setFont('Helvetica', 8.5)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.drawRightString(M + UW, cy - 8.5 * 0.85,
                          'Spelling Shed  \u2013  ' + ss_u + ' / ' + ss_p)
    cy -= 9 + 3 * mm

    c.setStrokeColorRGB(0.35, 0.35, 0.35)
    c.setLineWidth(0.6)
    c.line(M, cy, M + UW, cy)
    cy -= 3 * mm

    # Instruction text (includes full rule explanation if provided)
    rule_desc = rule_title
    if rule_explanation:
        rule_desc = rule_title + ' \u2013 ' + rule_explanation
    instruction = (
        'The first 5 words below are your Key Spellings. '
        'This week\u2019s spelling rule \u2013 ' + rule_desc + '. '
        'Practise spelling these words. Write each word within a sentence '
        'in the space below. These words will be checked in your paired spelling bee.'
    )
    c.setFont('Helvetica', 8.5)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    for il in simpleSplit(instruction, 'Helvetica', 8.5, UW):
        c.drawString(M, cy - 8.5 * 0.85, il)
        cy -= 8.5 * 1.35
    cy -= 2 * mm

    c.setStrokeColorRGB(0.35, 0.35, 0.35)
    c.setLineWidth(0.5)
    c.line(M, cy, M + UW, cy)
    cy -= 2 * mm

    # Word table
    table_top = cy
    table_bot = M + GLUE_H
    table_h   = table_top - table_bot
    all_words = list(key_words)[:5] + list(rule_words)[:5]
    n         = len(all_words)
    if n == 0:
        return

    row_h = table_h / n   # naturally ~15mm for 10 words

    # Outer rect + vertical divider
    c.setStrokeColorRGB(0.35, 0.35, 0.35)
    c.setLineWidth(0.6)
    c.rect(M, table_bot, UW, table_h, fill=0, stroke=1)
    c.setLineWidth(0.5)
    c.line(LINE_X, table_bot, LINE_X, table_top)

    for i, word in enumerate(all_words):
        row_top = table_top - i * row_h
        row_bot = row_top - row_h
        row_mid = (row_top + row_bot) / 2

        # Row divider (skip first — outer rect provides top)
        if i > 0:
            c.setStrokeColorRGB(0.50, 0.50, 0.50)
            c.setLineWidth(0.4)
            c.line(M, row_top, M + UW, row_top)

        # Mid-line in writing column: two writing sub-cells, no floating lines
        c.setStrokeColorRGB(0.55, 0.55, 0.55)
        c.setLineWidth(0.35)
        c.line(LINE_X, row_mid, M + UW, row_mid)

        # Word text — XCCW cursive 14pt, vertically centred in left cell
        is_key  = (i < 5)
        c.setFillColorRGB(*NAVY if is_key else (0.35, 0.35, 0.55))
        word_bl = row_mid - SPELL_FS * 0.35
        prefix = f'{i + 1}.  '
        c.setFont('Helvetica', SPELL_FS)
        num_w = c.stringWidth(prefix, 'Helvetica', SPELL_FS)
        c.drawString(M + 2.5 * mm, word_bl, prefix)
        _draw_xccw(c, M + 2.5 * mm + num_w, word_bl, str(word), SPELL_FS)

    # Redraw outer border and divider over row tints
    c.setStrokeColorRGB(0.35, 0.35, 0.35)
    c.setLineWidth(0.6)
    c.rect(M, table_bot, UW, table_h, fill=0, stroke=1)
    c.setLineWidth(0.5)
    c.line(LINE_X, table_bot, LINE_X, table_top)

    # Glue strip
    c.setFillColorRGB(0.95, 0.95, 0.95)
    c.rect(M, M, UW, GLUE_H - 1 * mm, fill=1, stroke=0)
    glue_txt = (' \u00b7 glue here \u00b7 ') * 30
    c.setFont('Helvetica-Oblique', 7)
    c.setFillColorRGB(0.70, 0.70, 0.70)
    for gl in simpleSplit(glue_txt, 'Helvetica-Oblique', 7, UW)[:1]:
        c.drawString(M, M + GLUE_H - 5.5 * mm, gl)


def build_hl_pdf(pupils, hl_config, weekly_config, version='standard',
                 rule_title='', rule_words=None, key_words_map=None,
                 rule_explanation=''):
    """Duplex-ready A4 landscape PDF. Returns PDF bytes."""
    import re as _re
    from word_bank import get_active_words

    cfg           = hl_config.get(version, hl_config.get('standard', {}))
    week_ref      = weekly_config.get('week_ref', 'TxWy')
    rule_words    = rule_words    or []
    key_words_map = key_words_map or {}

    _gs      = cfg.get('grid_size', 10) or 10
    grid_png = _hl_grid_png(cfg.get('grid_elements', []), grid_size=_gs)
    qr_png   = _hl_qr_png()

    buf = _io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=landscape(A4))

    _W, _H    = landscape(A4)
    _M        = 10 * mm
    _DIV      = 1.0
    _col_w    = (_W - 2 * _M - _DIV) / 2
    HEADER_H  = 14 * mm          # zone above outer table border for page title
    table_top = _H - _M - HEADER_H

    def _week_str(wr):
        m = _re.match(r'T(\d+)W(\d+)', wr)
        return ('Term ' + m.group(1) + ' Week ' + m.group(2)) if m else wr

    for pupil in pupils:
        left_x  = _M
        right_x = _M + _col_w + _DIV

        # Page header above the outer table border
        cx_      = _W / 2
        term_str = _week_str(week_ref)
        name     = pupil.get('first', '')
        c.setFont('Helvetica', 8.5)
        c.setFillColorRGB(*DGREY)
        c.drawCentredString(cx_, _H - _M - 8.5, term_str + ' Home Learning')
        c.setFont('Helvetica-Bold', 13)
        c.setFillColorRGB(*NAVY)
        c.drawCentredString(cx_, _H - _M - 8.5 - 3 - 13, name)

        # Maths column (left)
        _hl_maths_col(c, left_x, table_top, _col_w, table_top - _M,
                      pupil, cfg, week_ref, grid_png, qr_png)

        # Vertical column divider
        c.setStrokeColorRGB(0.35, 0.35, 0.35)
        c.setLineWidth(0.6)
        c.line(_M + _col_w + _DIV / 2, table_top, _M + _col_w + _DIV / 2, _M)

        # Reading column (right)
        _hl_reading_col(c, right_x, table_top, _col_w, table_top - _M, cfg)

        # Outer content border — drawn last so it sits on top of the grey TT bar
        c.setStrokeColorRGB(0.30, 0.30, 0.30)
        c.setLineWidth(0.8)
        c.rect(_M, _M, _W - 2 * _M, table_top - _M, fill=0, stroke=1)

        c.showPage()

        # Back: spelling
        kw = key_words_map.get(pupil.get('id', ''), [])
        if not kw:
            mastered = set(pupil.get('mastered', []))
            kw = get_active_words(pupil.get('word_pos', 0), mastered, count=5)
        _hl_spelling_page(c, pupil, rule_title, rule_words, kw, week_ref,
                          rule_explanation=rule_explanation)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()

# ── Handwriting practice sheet ─────────────────────────────────────────────────

_XCCW_DOT_REGISTERED = False

def _ensure_xccw_dotted():
    global _XCCW_DOT_REGISTERED
    if _XCCW_DOT_REGISTERED:
        return
    from reportlab.pdfbase.ttfonts import TTFont
    for name in ('XCCW_Joined_Dotted_4a', 'XCCW_Joined_Dotted_4b'):
        path = _os_hl.path.join(_FONT_DIR_HL, f'{name}.ttf')
        if _os_hl.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    _XCCW_DOT_REGISTERED = True


def _draw_xccw_dotted(c, x, y, text, size):
    """Draw text using dotted XCCW cursive with correct 4a/4b join variants."""
    _ensure_xccw_dotted()
    prev = None
    for ch in text:
        if prev and prev in _TOP_EXIT:
            font = 'XCCW_Joined_Dotted_4b'
        else:
            font = 'XCCW_Joined_Dotted_4a'
        try:
            c.setFont(font, size)
        except Exception:
            c.setFont('Helvetica', size)
        c.drawString(x, y, ch)
        try:
            x += pdfmetrics.stringWidth(ch, font, size)
        except Exception:
            x += pdfmetrics.stringWidth(ch, 'Helvetica', size)
        prev = ch if ch.strip() else None


def _xccw_dotted_width(text, size):
    _ensure_xccw_dotted()
    w = 0
    prev = None
    for ch in text:
        font = ('XCCW_Joined_Dotted_4b'
                if prev and prev in _TOP_EXIT
                else 'XCCW_Joined_Dotted_4a')
        try:
            w += pdfmetrics.stringWidth(ch, font, size)
        except Exception:
            w += pdfmetrics.stringWidth(ch, 'Helvetica', size)
        prev = ch if ch.strip() else None
    return w


def build_handwriting_sheet(words, week_ref, title='Handwriting Practice'):
    """
    A4 portrait. One ruled row per word — ascender guide + baseline.
    Dotted XCCW cursive at 26pt (8mm ascenders). Returns PDF bytes.
    """
    _ensure_xccw_dotted()

    buf = io.BytesIO()
    W, H = A4
    M    = 50   # pt margin left/right
    UW   = W - 2 * M

    # Row geometry — matches exercise book ruling
    FONT_SIZE  = 26       # pt
    ASC_H      = 22.86    # pt  ≈ 8.07 mm
    DESC_D     = 10.06    # pt  ≈ 3.55 mm
    LINE_GAP   = 7.09     # pt  ≈ 2.5 mm
    WORD_GAP   = 5.67     # pt  ≈ 2.0 mm

    # Row height: ascender + descent + gaps
    ROW_H = ASC_H + DESC_D + LINE_GAP + WORD_GAP

    c = canvas.Canvas(buf, pagesize=A4)

    # ── Header bar ────────────────────────────────────────────────────────
    HDR_H = 14 * mm
    c.setFillColorRGB(*BLUE)
    c.rect(0, H - HDR_H, W, HDR_H, fill=1, stroke=0)
    c.setFillColorRGB(*WHITE)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(M, H - HDR_H + (HDR_H - 10) / 2, title)
    c.setFont('Helvetica', 8)
    c.drawRightString(W - M, H - HDR_H + (HDR_H - 8) / 2,
                      f'{week_ref}  ·  Dotted XCCW cursive')

    TOP_Y = H - HDR_H - 10 * mm   # first ascender guide baseline

    page_words = []
    all_words  = list(words)

    def flush_page(page_words, is_first):
        nonlocal TOP_Y
        y = TOP_Y if is_first else H - HDR_H - 10 * mm
        for word in page_words:
            asc_y  = y               # ascender guide line
            base_y = y - ASC_H       # writing baseline

            # Ascender guide — light
            c.setStrokeColorRGB(0.75, 0.75, 0.75)
            c.setLineWidth(0.5)
            c.line(M, asc_y, M + UW, asc_y)

            # Baseline — slightly darker
            c.setStrokeColorRGB(0.50, 0.50, 0.50)
            c.setLineWidth(0.6)
            c.line(M, base_y, M + UW, base_y)

            # Dotted XCCW word
            c.setFillColorRGB(*NAVY)
            _draw_xccw_dotted(c, M, base_y, word, FONT_SIZE)

            y -= ROW_H

        c.showPage()

        # Re-draw header on subsequent pages
        c.setFillColorRGB(*BLUE)
        c.rect(0, H - HDR_H, W, HDR_H, fill=1, stroke=0)
        c.setFillColorRGB(*WHITE)
        c.setFont('Helvetica-Bold', 10)
        c.drawString(M, H - HDR_H + (HDR_H - 10) / 2, title)
        c.setFont('Helvetica', 8)
        c.drawRightString(W - M, H - HDR_H + (HDR_H - 8) / 2,
                          f'{week_ref}  ·  Dotted XCCW cursive')

    # Work out how many rows fit per page
    usable_h   = TOP_Y - (M + 10)
    rows_p1    = max(1, int(usable_h / ROW_H))
    usable_h2  = (H - HDR_H - 10 * mm) - (M + 10)
    rows_rest  = max(1, int(usable_h2 / ROW_H))

    # Paginate
    first_batch = all_words[:rows_p1]
    remaining   = all_words[rows_p1:]

    # Draw first page
    y = TOP_Y
    for word in first_batch:
        asc_y  = y
        base_y = y - ASC_H

        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.5)
        c.line(M, asc_y, M + UW, asc_y)

        c.setStrokeColorRGB(0.50, 0.50, 0.50)
        c.setLineWidth(0.6)
        c.line(M, base_y, M + UW, base_y)

        c.setFillColorRGB(*NAVY)
        _draw_xccw_dotted(c, M, base_y, word, FONT_SIZE)

        y -= ROW_H

    if first_batch:
        c.showPage()

    # Subsequent pages
    idx = 0
    while idx < len(remaining):
        batch = remaining[idx:idx + rows_rest]
        idx  += rows_rest

        c.setFillColorRGB(*BLUE)
        c.rect(0, H - HDR_H, W, HDR_H, fill=1, stroke=0)
        c.setFillColorRGB(*WHITE)
        c.setFont('Helvetica-Bold', 10)
        c.drawString(M, H - HDR_H + (HDR_H - 10) / 2, title)
        c.setFont('Helvetica', 8)
        c.drawRightString(W - M, H - HDR_H + (HDR_H - 8) / 2,
                          f'{week_ref}  ·  Dotted XCCW cursive')

        y = H - HDR_H - 10 * mm
        for word in batch:
            asc_y  = y
            base_y = y - ASC_H

            c.setStrokeColorRGB(0.75, 0.75, 0.75)
            c.setLineWidth(0.5)
            c.line(M, asc_y, M + UW, asc_y)

            c.setStrokeColorRGB(0.50, 0.50, 0.50)
            c.setLineWidth(0.6)
            c.line(M, base_y, M + UW, base_y)

            c.setFillColorRGB(*NAVY)
            _draw_xccw_dotted(c, M, base_y, word, FONT_SIZE)

            y -= ROW_H

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
