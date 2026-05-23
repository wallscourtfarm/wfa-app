from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_bee_pupils, save_bee_assessment

bee_bp = Blueprint('bee', __name__)
DEFAULT_CLASS = 'Y4_IM'

@bee_bp.route('/spelling-bee')
def spelling_bee():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    group_filter = request.args.get('group', 'all')
    pupils, rules_info, week_ref = load_bee_pupils(DEFAULT_CLASS)
    if group_filter != 'all':
        pupils = [p for p in pupils if p['group'] == group_filter]
    return render_template('bee.html', pupils=pupils, rules_info=rules_info,
                           week_ref=week_ref, group_filter=group_filter,
                           cls=DEFAULT_CLASS)

@bee_bp.route('/api/bee/save', methods=['POST'])
def api_bee_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body = request.get_json(force=True)
    cls  = body.get('cls', DEFAULT_CLASS)
    assessments = body.get('assessments', [])
    if not assessments:
        return jsonify({'ok': False, 'error': 'Nothing to save'})
    result = save_bee_assessment(cls, assessments)
    return jsonify(result)
