"""
data_manager.py
Reads and writes JSON data files stored in the wallscourtfarm/spelling-homelearning
GitHub repo. All functions are atomic: load → modify → save in one operation.

Environment variables required:
    GITHUB_TOKEN  — personal access token with repo write access
    DATA_REPO     — e.g. wallscourtfarm/spelling-homelearning
"""

import os
import json
import base64
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
DATA_REPO = os.environ.get('DATA_REPO', 'wallscourtfarm/spelling-homelearning')

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}

BASE_URL = f'https://api.github.com/repos/{DATA_REPO}/contents'


# ── GitHub helpers ────────────────────────────────────────────────────────────

def _get_file(path: str) -> tuple[dict, str]:
    """Return (parsed JSON, sha) for a file in the data repo."""
    r = requests.get(f'{BASE_URL}/{path}', headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return json.loads(content), data['sha']


def _put_file(path: str, data: dict, sha: str, message: str) -> None:
    """Write data back to a file in the data repo."""
    content = base64.b64encode(
        json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    ).decode('utf-8')
    payload = {
        'message': message,
        'content': content,
        'sha': sha,
    }
    r = requests.put(f'{BASE_URL}/{path}', headers=HEADERS,
                     json=payload, timeout=10)
    r.raise_for_status()


# ── Class / pupil helpers ─────────────────────────────────────────────────────

# Map short class codes used in the UI to the full IDs stored in JSON
YG_CLASS_IDS = {
    'IM': 'Y4_IM',
}


def class_id(cls: str) -> str:
    return YG_CLASS_IDS.get(cls, cls)


# ── TT Check ─────────────────────────────────────────────────────────────────

TT_DATA_PATH = 'data/tt_data.json'   # adjust if the real path differs


def load_tt_data(cls: str) -> list[dict]:
    """
    Return list of pupil dicts for the given class.
    Each dict has at minimum: name, current_tt, attempts, correct.
    """
    try:
        data, _ = _get_file(TT_DATA_PATH)
        cid = class_id(cls)
        return data.get(cid, {}).get('pupils', [])
    except Exception as e:
        return []   # caller handles empty gracefully


def advance_tt_pupils(cls: str, pupil_names: list[str]) -> dict:
    """
    Atomically advance TT stage for the named pupils.
    Returns {'ok': True} or {'ok': False, 'error': str}.
    """
    try:
        data, sha = _get_file(TT_DATA_PATH)
        cid = class_id(cls)
        class_data = data.setdefault(cid, {})
        pupils = class_data.setdefault('pupils', [])

        for pupil in pupils:
            if pupil.get('name') in pupil_names:
                pupil['current_tt'] = min(pupil.get('current_tt', 1) + 1, 12)
                pupil['attempts'] = 0
                pupil['correct'] = 0

        _put_file(TT_DATA_PATH, data, sha,
                  f'TT advance: {", ".join(pupil_names)} ({cls})')
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def save_tt_results(cls: str, results: list[dict]) -> dict:
    """
    Save updated attempt/correct counts for a pupil list.
    results: [{'name': str, 'attempts': int, 'correct': int}, ...]
    """
    try:
        data, sha = _get_file(TT_DATA_PATH)
        cid = class_id(cls)
        pupils = data.get(cid, {}).get('pupils', [])

        result_map = {r['name']: r for r in results}
        for pupil in pupils:
            if pupil['name'] in result_map:
                r = result_map[pupil['name']]
                pupil['attempts'] = r.get('attempts', pupil.get('attempts', 0))
                pupil['correct'] = r.get('correct', pupil.get('correct', 0))

        _put_file(TT_DATA_PATH, data, sha,
                  f'TT results update ({cls})')
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
