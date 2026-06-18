from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_bee_pupils, save_bee_assessment, update_rule_confidence_from_bee, YEAR_GROUP_CLASSES, _resolve_classes, get_class_options_for_year

bee_bp = Blueprint('bee', __name__)

@bee_bp.route('/spelling-bee')
def spelling_bee():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    yr           = session.get('year_group', '4')
    yr_classes   = YEAR_GROUP_CLASSES.get(yr, [])
    valid        = [f'Y{yr}_all'] + yr_classes
    cls          = request.args.get('cls', f'Y{yr}_all')
    if cls not in valid: cls = f'Y{yr}_all'
    group_filter = request.args.get('group', 'all')

    # Resolve _all to the actual classes for this year
    class_ids = _resolve_classes(cls)
    pupils, rules_info, week_ref = [], {}, ''
    for cid in class_ids:
        p, ri, wr = load_bee_pupils(cid)
        pupils += p
        if not rules_info: rules_info = ri
        if not week_ref:   week_ref   = wr

    if group_filter != 'all':
        pupils = [p for p in pupils if p['group'] == group_filter]

    class_options = get_class_options_for_year(yr)
    return render_template('bee.html', pupils=pupils, rules_info=rules_info,
                           week_ref=week_ref, group_filter=group_filter,
                           cls=cls, class_options=class_options, active_year=yr)

@bee_bp.route('/api/bee/save', methods=['POST'])
def api_bee_save():
    if not session.get('authenticated'):
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    body        = request.get_json(force=True)
    assessments = body.get('assessments', [])
    if not assessments:
        return jsonify({'ok': False, 'error': 'Nothing to save'})

    # Group assessments by class — fall back to top-level cls if not on each assessment
    cls_from_body = body.get('cls', '')
    by_class = {}
    for a in assessments:
        c = a.get('cls', '') or cls_from_body
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
