from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_tt_pupils, advance_tt_pupils, YEAR_GROUP_CLASSES

tt_bp = Blueprint('tt', __name__)


def require_auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))


def _default_cls():
    """Return the first class for the current session's year group."""
    yr = session.get('year_group', '4')
    classes = YEAR_GROUP_CLASSES.get(yr, ['4CK'])
    return classes[0] if classes else '4CK'


@tt_bp.route('/tt')
def tt_check():
    redir = require_auth()
    if redir:
        return redir
    cls    = request.args.get('cls', _default_cls())
    pupils = load_tt_pupils(cls)
    return render_template('tt_check.html', pupils=pupils, cls=cls)


@tt_bp.route('/api/tt/advance', methods=['POST'])
def api_tt_advance():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)
    cls  = body.get('cls', _default_cls())
    ids  = body.get('ids', [])
    if not ids:
        return jsonify({'ok': False, 'error': 'No pupils selected'})
    result = advance_tt_pupils(cls, ids)
    return jsonify(result)


@tt_bp.route('/api/tt/data')
def api_tt_data():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    cls    = request.args.get('cls', _default_cls())
    pupils = load_tt_pupils(cls)
    return jsonify({'ok': True, 'pupils': pupils})
