import json
from flask import Blueprint, render_template, session, redirect, url_for, request
from data_manager import load_dashboard, lowest_confidence_key_spellings, stuck_key_spellings, load_learners, TT_ORDER, ALL_CLASSES, get_class_options, get_class_options_for_year, get_ref_class
from routes.learners import _enrich, _homophone_words_by_stage
from names_display import labels_for_pupils, label_list

dash_bp = Blueprint('dash', __name__)
CLASS_OPTIONS = get_class_options()

@dash_bp.route('/dashboard')
def dashboard():
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
    # Privacy: the browser only ever gets initials labels, never names/UPNs.
    labels = labels_for_pupils(data['rows'])
    rows = []
    for r in data['rows']:
        r = {k: v for k, v in r.items() if k not in ('first', 'last', 'name', 'upn')}
        r['label'] = labels.get(r.get('id', ''), '')
        rows.append(r)
    learner_pupils = [{**{k: v for k, v in lp.items()
                          if k not in ('first', 'last', 'name', 'upn', 'pupil_id')},
                       'pid': lp.get('pupil_id', '')}
                      for lp in learner_pupils]
    # Children who have had the same key spelling for 2+ weeks (the page filters to 3+ by default).
    # Privacy: initials label + pupil code only; first/last never leave the server.
    try:
        stuck_raw = stuck_key_spellings(cls, min_weeks=2)
    except Exception:
        stuck_raw = []
    stuck_labels = label_list([(s.get('first', ''), s.get('last', '')) for s in stuck_raw])
    stuck_pupils = [{'key': s['key'], 'pid': s.get('pupil_id', ''), 'cls': s['cls'].lstrip('0123456789'),
                     'label': stuck_labels[i], 'words': s['words']}
                    for i, s in enumerate(stuck_raw)]
    return render_template('dashboard.html',
        rows=rows, stats=data['stats'], stuck_pupils=stuck_pupils,
        tt_labels=json.dumps(tt_labels), tt_values=json.dumps(tt_values),
        cls=cls, class_options=get_class_options_for_year(session.get("year_group","4")),
        lc_words=lc_words, active_year=yr,
        learner_pupils=learner_pupils)
