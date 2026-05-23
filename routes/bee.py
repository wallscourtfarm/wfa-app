from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_bee_pupils, save_bee_assessment

bee_bp = Blueprint('bee', __name__)
CLASSES = ['Y4_IM', 'Y4_WU']

@bee_bp.route('/spelling-bee')
def spelling_bee():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    cls          = request.args.get('cls', 'Y4_IM')
    if cls not in CLASSES:
        cls = 'Y4_IM'
    group_filter = request.args.get('group', 'all')
    pupils, rules_info, week_ref = load_bee_pupils(cls)
    if group_filter != 'all':
        pupils = [p for p in pupils if p['group'] == group_filter]
    return render_template('bee.html', pupils=pupils, rules_info=rules_info,
                           week_ref=week_ref, group_filter=group_filter,
                           cls=cls, classes=CLASSES)

@bee_bp.route('/api/bee/save', methods=['POST'])
def api_bee_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body        = request.get_json(force=True)
    cls         = body.get('cls', 'Y4_IM')
    assessments = body.get('assessments', [])
    if not assessments:
        return jsonify({'ok': False, 'error': 'Nothing to save'})
    return jsonify(save_bee_assessment(cls, assessments))
