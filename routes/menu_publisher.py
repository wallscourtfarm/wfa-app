import os
import re
import json
import base64
import requests as http_req
from datetime import date, datetime
from functools import wraps
from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, jsonify)

menu_bp = Blueprint("menu", __name__)

GITHUB_OWNER = "wallscourtfarm"
GITHUB_REPO  = "staff-tools"
GITHUB_PATH  = "menu.json"
DAYS         = ["Mon", "Tue", "Wed", "Thu", "Fri"]

EXTRACT_PROMPT = """You are extracting a UK primary school lunch menu from a PDF.

The menu has 3 weeks (Week 1, Week 2, Week 3) that rotate. Each page lists the dates
the week applies to (typically 8-10 Monday dates per page in DD/MM/YY format) and the
meal options for that week.

Each day has TWO main hot options:
- A "red column" option (typically meat-based, upper row)
- A "green column" option (vegetarian, lower row)

Days run Monday to Friday. Ignore the rotating "Filled Jackets" and "Pasta Twirler"
sections — those are fixed and not part of what we extract.

Keep meal names SHORT (under 40 chars). Drop "HALAL/NON HALAL" labels. Drop "Skin on".
Convert "&" to "and". Examples:
- "Roast Chicken, Stuffing, Roasties"
- "Fish Fingers and Chips"
- "Mixed Bean Fajitas with Wedges"

Return ONLY valid JSON in this exact structure (no markdown, no commentary):
{
  "term_label": "Spring/Summer 2026",
  "weeks": [
    {
      "week_number": 1,
      "monday_dates": ["2026-04-13", "2026-05-04"],
      "days": {
        "Mon": ["Red option", "Green option"],
        "Tue": ["...", "..."],
        "Wed": ["...", "..."],
        "Thu": ["...", "..."],
        "Fri": ["...", "..."]
      }
    }
  ]
}

Convert all dates to YYYY-MM-DD. If the PDF shows "13/04/26" assume 2026."""


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def _fetch_current_menu():
    try:
        r = http_req.get(
            f"https://wallscourtfarm.github.io/{GITHUB_REPO}/{GITHUB_PATH}",
            timeout=5,
            params={"t": datetime.now().isoformat()},
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _expand_to_weekly_menu(extracted):
    weeks_out = {}
    for week in extracted["weeks"]:
        for monday in week["monday_dates"]:
            weeks_out[monday] = week["days"]
    sorted_weeks = {k: weeks_out[k] for k in sorted(weeks_out.keys())}
    return {
        "_comment": "WFA shared lunch menu. Each key is a Monday in YYYY-MM-DD. Each day holds [red_option, green_option].",
        "_lastUpdated": date.today().isoformat(),
        "_termLabel": extracted.get("term_label", ""),
        "weeks": sorted_weeks,
    }


def _publish_to_github(menu_dict, commit_message):
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if not gh_token:
        raise RuntimeError("GITHUB_TOKEN not set in Render environment variables.")
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    r = http_req.get(url, headers=headers, timeout=10)
    sha = r.json().get("sha") if r.status_code == 200 else None

    content_b64 = base64.standard_b64encode(
        json.dumps(menu_dict, indent=2).encode("utf-8")
    ).decode("utf-8")
    body = {"message": commit_message, "content": content_b64}
    if sha:
        body["sha"] = sha

    r = http_req.put(url, headers=headers, json=body, timeout=15)
    if r.status_code in (200, 201):
        return r.json()["commit"]["html_url"]
    raise RuntimeError(f"GitHub PUT failed: {r.status_code} {r.text[:200]}")


# ── Routes ────────────────────────────────────────────────────────────────────

@menu_bp.route("/menu")
@require_auth
def menu_home():
    current = _fetch_current_menu()
    return render_template("menu_publisher.html", current=current)


@menu_bp.route("/menu/extract", methods=["POST"])
@require_auth
def menu_extract():
    if "pdf" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["pdf"]
    pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": EXTRACT_PROMPT},
                ],
            }],
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        extracted = json.loads(text)
        menu = _expand_to_weekly_menu(extracted)
        return jsonify({"ok": True, "menu": menu})
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Claude returned invalid JSON: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@menu_bp.route("/menu/publish", methods=["POST"])
@require_auth
def menu_publish():
    data = request.get_json()
    if not data or "menu" not in data:
        return jsonify({"error": "No menu data"}), 400
    try:
        commit_url = _publish_to_github(data["menu"], data.get("message", "Update menu (via WFA app)"))
        return jsonify({"ok": True, "commit_url": commit_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
