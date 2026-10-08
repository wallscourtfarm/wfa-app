"""Name-free identity for scanned assessment sheets (shared by word / rule / homophone).

A pupil's printed sheet carries two things in its header strip, and NO name:
  * the pupil's INITIALS label (names_display, clash-aware across the printed class), and
  * the pupil's CODE, i.e. their pupil_id (e.g. p_k3m9x2q7ab), in large monospaced text.

When the completed stack is scanned, the AI is asked to read the CODE (never a name).
match_code() turns what it returned into one of the class's pupils. Everything sent to the
browser uses only the initials label and a status; real names never leave the server and are
never sent to the AI.

Pupils with no pupil_id (older session data) print initials plus "No code"; those pages come
back 'unmatched' and the teacher assigns them by hand from a dropdown of initials labels.
Their key is "<class_id>|<id>" (the existing p01-style id is only unique inside one class).
"""
import re
import unicodedata

from names_display import label_list

ALPHABET = 'abcdefghijklmnopqrstuvwxyz234567'
_DIGIT_FIX = str.maketrans({'0': 'o', '1': 'l', '8': 'b', '9': 'g'})

# Instruction block for the vision prompt. Deliberately says nothing about names.
CODE_PROMPT = (
    "At the top of the page, in the header strip, a short code like p_xxxxxxxxxx is printed in large "
    "typewriter-style letters after the word 'Code:'. Return that code exactly as printed, character "
    "for character. If there is no code, or it is not legible, return an empty string for it."
)


# ── Keys, labels, sheet identity ─────────────────────────────────────────────

def pupil_code(pupil):
    """The code to print for a pupil, or '' if they have none."""
    pid = (pupil.get('pupil_id') or '').strip()
    return pid


def pupil_key(class_id, pupil):
    """Stable key the browser and confirm route use: the pupil_id, else '<class>|<id>'."""
    return pupil_code(pupil) or f"{class_id}|{pupil.get('id', '')}"


def labels_for(pupils):
    """Initials labels for a list of pupil dicts, same order, clash-aware across the list."""
    pupils = list(pupils)
    return label_list([(p.get('first') or '', p.get('last') or '') for p in pupils])


def roster(entries):
    """entries: [(class_id, pupil_dict)] -> [{'key','label','has_code'}] (labels only, no names)."""
    entries = list(entries)
    labels = labels_for([p for _, p in entries])
    return [{'key': pupil_key(cid, p), 'label': labels[i], 'has_code': bool(pupil_code(p))}
            for i, (cid, p) in enumerate(entries)]


def expected_ids(entries):
    return [pupil_code(p) for _, p in entries if pupil_code(p)]


# ── Code matching ────────────────────────────────────────────────────────────

def _normalise(returned):
    """Lower-case; drop spaces, zero-width and punctuation (keeping '_'); find the 'p_' prefix;
    map 0/1/8/9 (never in the alphabet) to o/l/b/g. Returns '' if there is no 'p_' prefix."""
    if not isinstance(returned, str):
        return ''
    s = unicodedata.normalize('NFKC', returned).lower()
    s = ''.join(ch for ch in s if ch.isascii() and (ch.isalnum() or ch == '_'))
    i = s.find('p_')
    if i < 0:
        return ''
    return 'p_' + s[i + 2:].translate(_DIGIT_FIX)


def _within_one(a, b):
    """True if Levenshtein distance(a, b) <= 1 (and a != b)."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if la < lb else (b, a)
    for i in range(len(l)):
        if l[:i] + l[i + 1:] == s:
            return True
    return False


def match_code(returned, expected_ids):
    """-> (pupil_id or None, status) with status in 'matched' | 'fuzzy' | 'unmatched'.
    Exact match first; else a UNIQUE expected id within edit distance 1 ('fuzzy'); else unmatched."""
    cand = _normalise(returned)
    if len(cand) <= 2:
        return None, 'unmatched'
    exp = sorted({e.strip().lower() for e in expected_ids if isinstance(e, str) and e.strip()})
    if cand in exp:
        return cand, 'matched'
    near = [e for e in exp if _within_one(cand, e)]
    if len(near) == 1:
        return near[0], 'fuzzy'
    return None, 'unmatched'


# ── Printing ─────────────────────────────────────────────────────────────────

def draw_scan_header(c, W, H, label, code, week_ref, page_label, assessment_type="Word Assessment"):
    """Fixed header strip: initials + large monospaced code, no name. Returns y below the strip.
    Black on white (not white on grey) so the code survives photocopying and scanning."""
    from reportlab.lib.units import mm
    HDR = 14 * mm
    top = H - HDR
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, top, W, HDR, fill=1, stroke=0)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.2)
    c.line(0, top, W, top)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(10 * mm, top + (HDR - 15) / 2 + 1, label)
    if code:
        text = f"Code: {code}"
        c.setFont("Courier-Bold", 17)
        x = 48 * mm
        tw = c.stringWidth(text, "Courier-Bold", 17)
        c.setLineWidth(0.8)
        c.rect(x - 2 * mm, top + 2.5 * mm, tw + 4 * mm, HDR - 5 * mm, fill=0, stroke=1)
        c.drawString(x, top + (HDR - 17) / 2 + 2.5, text)
    else:
        c.setFont("Helvetica", 9)
        c.drawString(48 * mm, top + (HDR - 9) / 2, "No code (match by hand)")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 10 * mm, top + (HDR - 8) / 2,
                      f"{assessment_type}  ·  {week_ref}  ·  {page_label}")
    return top
