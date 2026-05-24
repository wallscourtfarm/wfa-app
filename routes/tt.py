from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_tt_pupils, advance_tt_pupils

tt_bp = Blueprint('tt', __name__)
# DEFAULT_CLASS now derived from session


def require_auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))


@tt_bp.route('/tt')
def tt_check():
    redir = require_auth()
    if redir:
        return redir
    pupils = load_tt_pupils(DEFAULT_CLASS)
    return render_template('tt_check.html', pupils=pupils, cls=DEFAULT_CLASS)


@tt_bp.route('/api/tt/advance', methods=['POST'])
def api_tt_advance():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)
    cls  = body.get('cls', DEFAULT_CLASS)
    ids  = body.get('ids', [])
    if not ids:
        return jsonify({'ok': False, 'error': 'No pupils selected'})
    result = advance_tt_pupils(cls, ids)
    return jsonify(result)


@tt_bp.route('/api/tt/data')
def api_tt_data():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    yr  = session.get('year_group', '4')
    from data_manager import YEAR_GROUP_CLASSES
    _yr_cls = YEAR_GROUP_CLASSES.get(yr, ['Y4_IM'])
    cls = request.args.get('cls', _yr_cls[0] if _yr_cls else 'Y4_IM')
    pupils = load_tt_pupils(cls)
    return jsonify({'ok': True, 'pupils': pupils})
