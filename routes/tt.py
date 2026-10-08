from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from data_manager import load_tt_pupils, advance_tt_pupils, YEAR_GROUP_CLASSES, get_class_options_for_year, _resolve_classes

from names_display import labels_for_pupils

tt_bp = Blueprint('tt', __name__)



def _default_cls():
    """Default to the whole year group for the current session."""
    return f"Y{session.get('year_group', '4')}_all"


def _public_pupils(pupils):
    """Replace names with an initials label; the browser never gets names."""
    labels = labels_for_pupils(pupils)
    return [{'id': p['id'], 'label': labels.get(p['id'], ''), 'tt_set': p['tt_set'],
             'tt_mode': p['tt_mode'], 'tt_label': p['label'], 'cls': p['cls']}
            for p in pupils]


def _valid_cls(cls):
    yr = session.get('year_group', '4')
    opts = [o[0] for o in get_class_options_for_year(yr)]
    return cls if cls in opts else _default_cls()


@tt_bp.route('/tt')
def tt_check():
    cls    = _valid_cls(request.args.get('cls', _default_cls()))
    pupils = _public_pupils(load_tt_pupils(cls))
    opts   = get_class_options_for_year(session.get('year_group', '4'))
    return render_template('tt_check.html', pupils=pupils, cls=cls,
                           class_options=opts,
                           cls_label=dict(opts).get(cls, cls))


@tt_bp.route('/api/tt/advance', methods=['POST'])
def api_tt_advance():
    body = request.get_json(force=True)
    cls  = _valid_cls(body.get('cls', _default_cls()))
    ids  = body.get('ids', [])
    if not ids:
        return jsonify({'ok': False, 'error': 'No pupils selected'})
    total = 0
    for cid in _resolve_classes(cls):
        result = advance_tt_pupils(cid, ids)
        if not result.get('ok'):
            return jsonify(result)
        total += result.get('count', 0)
    return jsonify({'ok': True, 'count': total})


@tt_bp.route('/api/tt/data')
def api_tt_data():
    cls    = _valid_cls(request.args.get('cls', _default_cls()))
    pupils = _public_pupils(load_tt_pupils(cls))
    return jsonify({'ok': True, 'pupils': pupils})
