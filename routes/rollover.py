"""
routes/rollover.py
Year-end rollover tool — promote pupils from one year group to the next.
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import YEAR_GROUP_CLASSES, get_year_counts, year_end_rollover

rollover_bp = Blueprint('rollover', __name__)

def _auth():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))

@rollover_bp.route('/rollover')
def rollover_page():
    r = _auth()
    if r: return r
    return render_template('rollover.html')

@rollover_bp.route('/api/rollover/counts')
def api_rollover_counts():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        counts = get_year_counts()
        return jsonify({'ok': True, 'counts': counts,
                        'year_order': list(YEAR_GROUP_CLASSES.keys())})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@rollover_bp.route('/api/rollover', methods=['POST'])
def api_rollover():
    r = _auth()
    if r: return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    try:
        body       = request.get_json(force=True)
        year_group = str(body.get('year_group', ''))
        if not year_group:
            return jsonify({'ok': False, 'error': 'year_group is required'})
        result = year_end_rollover(year_group)
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
