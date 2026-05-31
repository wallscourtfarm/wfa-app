import os, io, tempfile
from functools import wraps
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, send_file, jsonify)

wp_bp = Blueprint("wordpuzzles", __name__)

YEAR_GROUPS = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]


def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def _api_key():
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _send_pdf(pdf_bytes: bytes, filename: str):
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


@wp_bp.route("/puzzles")
@require_auth
def puzzles_home():
    return render_template("word_puzzles.html",
                           year_groups=YEAR_GROUPS,
                           difficulties=DIFFICULTIES)


# ── Word Search ───────────────────────────────────────────────────────────────

@wp_bp.route("/puzzles/word-search", methods=["POST"])
@require_auth
def word_search():
    from wordpuzzles.puzzles.word_search import generate_word_search
    from wordpuzzles.pdf_output.word_search_pdf import render_word_search_pdf
    from wordpuzzles.utils import get_words_from_topic

    topic      = request.form.get("topic", "").strip()
    year_group = request.form.get("year_group", "Y4")
    difficulty = request.form.get("difficulty", "Medium")
    word_list  = request.form.get("word_list", "").strip()

    if word_list:
        words = [w.strip().upper() for w in word_list.replace(",", "\n").splitlines() if w.strip()]
        display_title = topic or "Word Search"
    else:
        if not topic:
            return jsonify({"error": "Please enter a topic or word list"}), 400
        words, display_title = get_words_from_topic(topic, year_group, "word search",
                                                     n=16, api_key=_api_key())
        if not words:
            return jsonify({"error": f"Could not generate words for \"{topic}\""}), 400

    size = {"Easy": 10, "Medium": 12, "Hard": 15}.get(difficulty, 12)
    try:
        puzzle = generate_word_search(words, size=size, difficulty=difficulty)
        pdf    = render_word_search_pdf(puzzle, display_title, year_group)
        return _send_pdf(pdf, f"word_search_{display_title.lower().replace(' ','_')}.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Nine Letters ──────────────────────────────────────────────────────────────

@wp_bp.route("/puzzles/nine-letters", methods=["POST"])
@require_auth
def nine_letters():
    from wordpuzzles.puzzles.nine_letters import generate_nine_letters
    from wordpuzzles.pdf_output.nine_letters_pdf import render_nine_letters_pdf

    topic      = request.form.get("topic", "").strip()
    year_group = request.form.get("year_group", "Y4")

    if not topic:
        return jsonify({"error": "Please enter a topic"}), 400
    try:
        puzzle = generate_nine_letters(topic, year_group, _api_key())
        pdf    = render_nine_letters_pdf(puzzle, year_group)
        return _send_pdf(pdf, f"nine_letters_{topic.lower().replace(' ','_')}.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Word Ladder ───────────────────────────────────────────────────────────────

@wp_bp.route("/puzzles/word-ladder", methods=["POST"])
@require_auth
def word_ladder():
    from wordpuzzles.puzzles.word_ladder import generate_word_ladder
    from wordpuzzles.pdf_output.word_ladder_pdf import render_word_ladder_pdf

    topic      = request.form.get("topic", "").strip()
    year_group = request.form.get("year_group", "Y4")
    difficulty = request.form.get("difficulty", "Medium")

    if not topic:
        return jsonify({"error": "Please enter a topic"}), 400
    try:
        puzzle = generate_word_ladder(topic, year_group, difficulty, _api_key())
        pdf    = render_word_ladder_pdf(puzzle, topic, year_group)
        return _send_pdf(pdf, f"word_ladder_{topic.lower().replace(' ','_')}.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Word Scramble ─────────────────────────────────────────────────────────────

@wp_bp.route("/puzzles/word-scramble", methods=["POST"])
@require_auth
def word_scramble():
    from wordpuzzles.puzzles.word_scramble import generate_word_scramble
    from wordpuzzles.pdf_output.word_scramble_pdf import render_word_scramble_pdf
    from wordpuzzles.utils import get_words_from_topic

    topic      = request.form.get("topic", "").strip()
    year_group = request.form.get("year_group", "Y4")
    difficulty = request.form.get("difficulty", "Medium")
    word_list  = request.form.get("word_list", "").strip()

    if word_list:
        words = [w.strip() for w in word_list.replace(",", "\n").splitlines() if w.strip()]
        display_title = topic or "Word Scramble"
    else:
        if not topic:
            return jsonify({"error": "Please enter a topic or word list"}), 400
        words, display_title = get_words_from_topic(topic, year_group, "word scramble",
                                                     n=12, api_key=_api_key())
        if not words:
            return jsonify({"error": f"Could not generate words for \"{topic}\""}), 400

    try:
        puzzle = generate_word_scramble(words, difficulty=difficulty)
        pdf    = render_word_scramble_pdf(puzzle, display_title, year_group)
        return _send_pdf(pdf, f"word_scramble_{display_title.lower().replace(' ','_')}.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Cloze Passage ─────────────────────────────────────────────────────────────

@wp_bp.route("/puzzles/cloze", methods=["POST"])
@require_auth
def cloze_passage():
    from wordpuzzles.puzzles.cloze_passage import generate_cloze
    from wordpuzzles.pdf_output.cloze_passage_pdf import render_cloze_pdf

    topic      = request.form.get("topic", "").strip()
    year_group = request.form.get("year_group", "Y4")
    difficulty = request.form.get("difficulty", "Medium")

    if not topic:
        return jsonify({"error": "Please enter a topic"}), 400
    try:
        puzzle = generate_cloze(topic, year_group, difficulty, _api_key())
        pdf    = render_cloze_pdf(puzzle, topic, year_group)
        return _send_pdf(pdf, f"cloze_{topic.lower().replace(' ','_')}.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
