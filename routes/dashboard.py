import json
from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_dashboard, lowest_confidence_key_spellings, load_learners, TT_ORDER, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class
from routes.learners import _enrich, _homophone_words_by_stage

dash_bp = Blueprint('dash', __name__)
CLASS_OPTIONS = get_class_options()

@dash_bp.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    yr  = session.get('year_group', '4')
    cls = request.args.get('cls', f'Y{yr}_all')
    yr  = session.get('year_group', '4')
    valid = [c[0] for c in get_class_options_for_year(yr)]
    if cls not in valid: cls = f'Y{yr}_all'
    data = load_dashboard(cls)
    if not data:
        return render_template('dashboard.html', error=True, cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")))
    tt_labels = [f'×{t}' if t!='All' else 'All' for t in TT_ORDER]
    tt_values = [data['tt_dist'].get(t,0) for t in TT_ORDER]
    yr_for_lc = yr
    lc_words = lowest_confidence_key_spellings(cls, year=yr_for_lc, top_n=10)
    raw_pupils = load_learners(cls)
    hw_by_stage = _homophone_words_by_stage()
    learner_pupils = _enrich(raw_pupils, hw_by_stage)
    return render_template('dashboard.html',
        rows=data['rows'], stats=data['stats'],
        tt_labels=json.dumps(tt_labels), tt_values=json.dumps(tt_values),
        cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")),
        lc_words=lc_words, active_year=yr,
        learner_pupils=learner_pupils)
