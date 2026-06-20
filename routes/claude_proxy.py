"""Proxy endpoint for browser tools that need to call the Anthropic API.

Staff tools on staff.wallscourt-farm-academy.co.uk call POST /api/claude
with {system, messages, max_tokens} — this forwards the request using the
server-side API key so the key never appears in browser source.
"""

import os
from flask import Blueprint, request, jsonify
from claude_api import create_message, MODEL_FALLBACKS
import anthropic

proxy_bp = Blueprint("proxy", __name__)

ALLOWED_ORIGINS = {
    "https://staff.wallscourt-farm-academy.co.uk",
    "https://app.wallscourt-farm-academy.co.uk",
}


def _cors(response, origin):
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


@proxy_bp.route("/api/claude", methods=["POST", "OPTIONS"])
def claude_proxy():
    origin = request.headers.get("Origin", "")

    if origin not in ALLOWED_ORIGINS:
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    if request.method == "OPTIONS":
        return _cors(jsonify({}), origin)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _cors(jsonify({"ok": False, "error": "Server API key not configured"}), origin), 500

    body = request.get_json(silent=True) or {}
    kwargs = {"max_tokens": int(body.get("max_tokens", 2000))}
    if body.get("system"):
        kwargs["system"] = body["system"]
    if body.get("messages"):
        kwargs["messages"] = body["messages"]

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = create_message(client, **kwargs)
        text = msg.content[0].text if msg.content else ""
        return _cors(jsonify({"ok": True, "text": text, "model": msg.model}), origin)
    except anthropic.AuthenticationError:
        return _cors(jsonify({"ok": False, "error": "Invalid API key on server"}), origin), 500
    except Exception as exc:
        return _cors(jsonify({"ok": False, "error": str(exc)}), origin), 500
