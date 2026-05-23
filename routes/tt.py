from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_tt_data, advance_tt_pupils, save_tt_results

tt_bp = Blueprint('tt', __name__)

DEFAULT_CLASS = 'IM'


def require_auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    return None


@tt_bp.route('/tt')
def tt_check():
    redir = require_auth()
    if redir:
        return redir
    pupils = load_tt_data(DEFAULT_CLASS)
    return render_template('tt_check.html', pupils=pupils, cls=DEFAULT_CLASS)


@tt_bp.route('/api/tt/advance', methods=['POST'])
def api_tt_advance():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)
    cls = body.get('cls', DEFAULT_CLASS)
    names = body.get('names', [])
    if not names:
        return jsonify({'ok': False, 'error': 'No pupils selected'})
    result = advance_tt_pupils(cls, names)
    return jsonify(result)


@tt_bp.route('/api/tt/save', methods=['POST'])
def api_tt_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)
    cls = body.get('cls', DEFAULT_CLASS)
    results = body.get('results', [])
    result = save_tt_results(cls, results)
    return jsonify(result)


@tt_bp.route('/api/tt/data')
def api_tt_data():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    cls = request.args.get('cls', DEFAULT_CLASS)
    pupils = load_tt_data(cls)
    return jsonify({'ok': True, 'pupils': pupils})
