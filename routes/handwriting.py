import os, io, tempfile
from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, send_file

hw_bp = Blueprint("handwriting", __name__)

FONT_MAP = {
    "sassoon": "sassoon",
    "linkpen":  "linkpen",
    "xccw":     "xccw",
}


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@hw_bp.route("/handwriting")
@require_auth
def handwriting_home():
    return render_template("handwriting.html")


@hw_bp.route("/handwriting/generate", methods=["POST"])
@require_auth
def handwriting_generate():
    import handwriting_sheet as hs

    title       = request.form.get("title", "Handwriting Practice")[:80]
    raw_content = request.form.get("content", "")
    font_key    = request.form.get("font", "sassoon")
    practice    = int(request.form.get("practice_lines", "0") or "0")

    lines = [l.strip() for l in raw_content.splitlines() if l.strip()]
    if not lines:
        return render_template("handwriting.html", error="Please enter at least one word or sentence."), 400

    rows = [{"type": "word", "text": line} for line in lines]

    hs._ensure_fonts()

    if font_key == "sassoon":
        ascend, descend = hs.SASS_ASCEND, hs.SASS_DESCEND
        draw_fn, fs     = hs._draw_sassoon, hs.SASS_FS
    elif font_key == "linkpen":
        ascend, descend = hs.LINK_ASCEND, hs.LINK_DESCEND
        draw_fn, fs     = hs._draw_linkpen, hs.LINK_FS
    else:  # xccw
        ascend, descend = hs.XCCW_ASCEND, hs.XCCW_DESCEND
        draw_fn = lambda c, x, y, text, size: hs._draw_xccw(c, x, y, text, size, solid=False)
        fs      = hs.XCCW_FS

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp = f.name

    try:
        hs._generate_pdf(tmp, rows, title, None, ascend, descend, draw_fn, fs,
                         practice_lines=practice)
        safe = title.replace(" ", "_").lower()
        return send_file(tmp, mimetype="application/pdf",
                         as_attachment=True, download_name=f"{safe}.pdf")
    except Exception as e:
        return render_template("handwriting.html", error=f"Generation failed: {e}"), 500
