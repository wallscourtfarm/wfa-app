"""Spelling evidence is also keyed by pupil code, so the Tracker can join without any UPN. FAKE DATA ONLY."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("HUB_TOKEN", "h")

from flask import Flask  # noqa: E402

import routes.evidence as ev  # noqa: E402


def client(monkeypatch):
    monkeypatch.setenv("HUB_TOKEN", "h")
    monkeypatch.setattr(ev, "_resolve_classes", lambda x: ["c1"])
    monkeypatch.setattr(ev, "load_class", lambda cid: {"pupils": [
        {"upn": "U1", "pupil_id": "p_aaaaaaaaaa", "mastered": [], "rule_confidence": {}},
        {"pupil_id": "p_bbbbbbbbbb", "mastered": [], "rule_confidence": {}},          # no UPN any more
        {"mastered": []},                                                              # neither: ignored
    ]})
    monkeypatch.setattr(ev.word_bank, "mastery_stats", lambda s: {"Y5": 10})
    app = Flask(__name__)
    app.register_blueprint(ev.evidence_bp)
    return app.test_client()


def test_keyed_by_upn_and_by_code(monkeypatch):
    r = client(monkeypatch).get("/api/evidence/spelling/Y5?token=h").get_json()
    assert sorted(r["spelling"]) == ["U1"] and sorted(r["spelling_by_code"]) == ["p_aaaaaaaaaa", "p_bbbbbbbbbb"]
    assert r["spelling_by_code"]["p_aaaaaaaaaa"]["mastered_pct"] == 10


def test_still_needs_the_token(monkeypatch):
    assert client(monkeypatch).get("/api/evidence/spelling/Y5?token=bad").status_code == 401


def test_stuck_spellings_by_code_only(monkeypatch):
    seen = {}
    def fake(cls, min_weeks):
        seen.update(cls=cls, min_weeks=min_weeks)
        return [{'pupil_id': 'p_aaaaaaaaaa', 'first': 'Real', 'last': 'Name', 'words': [{'word': 'because', 'weeks': ['T1W2', 'T1W4'], 'n': 2}]},
                {'pupil_id': '', 'first': 'No', 'last': 'Code', 'words': [{'word': 'said', 'weeks': ['T1W1', 'T1W2'], 'n': 2}]}]
    monkeypatch.setattr(ev, "stuck_key_spellings", fake)
    c = client(monkeypatch)
    r = c.get("/api/evidence/stuck-spellings/Y5?token=h&min_weeks=3")
    assert r.get_json() == {'by_code': {'p_aaaaaaaaaa': [{'word': 'because', 'n': 2}]}}
    assert seen == {'cls': 'Y5_all', 'min_weeks': 3}
    assert 'Real' not in r.get_data(as_text=True)
    assert c.get("/api/evidence/stuck-spellings/Y5?token=bad").status_code == 401
    assert c.get("/api/evidence/stuck-spellings/R?token=h").get_json() == {'by_code': {}}
