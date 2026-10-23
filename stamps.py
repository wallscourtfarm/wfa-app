"""Name stamps (privacy plan, 18.10.26).

Printed sheets are drawn with each child's INITIALS. Every place where a real name could later be written is
logged here (position, size, colours, the child's pupil_id) and the log is embedded in the PDF's /Keywords as
"WFASTAMPS2:" + JSON. The teacher's own browser (static/print-names.js, WFAPrint.stampPdf) reads the log and writes
the real names over the initials using the names file held in that browser. Real names never reach this server.

Usage in a route:   stamps.begin();  data = build_...(...);  data = stamps.finish(data)
Usage in a builder: stamps.log(c, x, y, text, size, pupil_id, ...)   (no-op when begin() was not called)
"""
import io
import json
import threading

_T = threading.local()


def begin():
    _T.log = []


def take():
    out = getattr(_T, 'log', None) or []
    _T.log = None
    return out


def log(c, x, y, text, size, pupil_id, mode='f', bold=True, align='l', cover=(1, 1, 1),
        color=(0, 0, 0), prefix='', pill=None, cover_h=None, post=''):
    """Record one name slot. mode 'f' = first name, 'n' = first + last. align 'l' (x = left edge) or 'c' (x = centre).
    post = fixed text drawn straight after the name (e.g. "  |  Key spellings"), redrawn with it in the browser.
    cover = colour of the background behind the text (painted over the initials); pill = (x, y, h, pad, radius)
    when the text sits in a white pill whose width follows the name."""
    log_ = getattr(_T, 'log', None)
    if log_ is None or not pupil_id:
        return
    font = 'Helvetica-Bold' if bold else 'Helvetica'
    full = (prefix or '') + (text or '') + (post or '')
    rec = {'pg': c.getPageNumber() - 1, 'id': pupil_id, 'x': round(x, 2), 'y': round(y, 2),
           'w': round(c.stringWidth(full, font, size), 2), 's': size, 'm': mode, 'a': align, 'b': 1 if bold else 0,
           'cv': [round(v, 3) for v in cover], 'tc': [round(v, 3) for v in color]}
    if prefix:
        rec['pre'] = prefix
        rec['pw'] = round(c.stringWidth(prefix, font, size), 2)
    if post:
        rec['pst'] = post
    if cover_h:
        rec['ch'] = cover_h
    if pill:
        rec['pill'] = [round(v, 2) for v in pill]
    log_.append(rec)


def embed(pdf_bytes, stamps):
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf_bytes)))
    w.add_metadata({'/Keywords': 'WFASTAMPS2:' + json.dumps(stamps, separators=(',', ':'))})
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def finish(pdf_bytes):
    return embed(pdf_bytes, take())
