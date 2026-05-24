from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_bee_pupils, save_bee_assessment, update_rule_confidence_from_bee

bee_bp = Blueprint('bee', __name__)
VALID_CLASSES = ['Y4_IM', 'Y4_WU', 'Y4_all'] + __import__('data_manager').ALL_CLASSES

@bee_bp.route('/spelling-bee')
def spelling_bee():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    cls          = request.args.get('cls', 'all')
    if cls not in VALID_CLASSES: cls = 'all'
    group_filter = request.args.get('group', 'all')

    if cls == 'all':
        # Load both classes and merge
        pupils, rules_info, week_ref = load_bee_pupils('Y4_IM')
        pupils_wu, _, _ = load_bee_pupils('Y4_WU')
        pupils = pupils + pupils_wu
    else:
        pupils, rules_info, week_ref = load_bee_pupils(cls)

    if group_filter != 'all':
        pupils = [p for p in pupils if p['group'] == group_filter]

    return render_template('bee.html', pupils=pupils, rules_info=rules_info,
                           week_ref=week_ref, group_filter=group_filter,
                           cls=cls)

@bee_bp.route('/api/bee/save', methods=['POST'])
def api_bee_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body        = request.get_json(force=True)
    assessments = body.get('assessments', [])
    if not assessments:
        return jsonify({'ok': False, 'error': 'Nothing to save'})

    # Group assessments by class (pupil cls field)
    by_class = {}
    for a in assessments:
        c = a.get('cls', 'Y4_IM')
        by_class.setdefault(c, []).append(a)

    total_saved = 0
    for cls_id, ass_list in by_class.items():
        result = save_bee_assessment(cls_id, ass_list)
        if not result.get('ok'):
            return jsonify(result)
        total_saved += result.get('saved', 0)

    # Update rule confidence dots based on confident flags
    update_rule_confidence_from_bee(assessments)

    return jsonify({'ok': True, 'saved': total_saved})
