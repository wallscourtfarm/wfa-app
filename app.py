import os
from flask import Flask

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_any_exception(e):
    import traceback
    from flask import jsonify
    return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()[-800:]}), 500
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

from routes.auth          import auth_bp
from routes.dashboard     import dash_bp
from routes.tt            import tt_bp
from routes.bee           import bee_bp
from routes.learners      import learners_bp
from routes.home_learning import hl_bp
from routes.settings      import settings_bp
from routes.rules         import rules_bp
from routes.stubs         import stubs_bp
from routes.print_tools   import print_bp
from routes.word_assessment import wa_bp
from routes.rule_assessment  import ra_bp
from routes.homophone_assessment import ha_bp
from routes.insights import insights_bp
from routes.digital_sessions import live_bp
from routes.class_manager import cm_bp
from routes.rollover import rollover_bp
from routes.menu_publisher import menu_bp
from routes.handwriting import hw_bp
from routes.word_puzzles import wp_bp

for bp in [auth_bp, dash_bp, tt_bp, bee_bp, learners_bp, hl_bp, settings_bp, rules_bp, stubs_bp, print_bp, wa_bp, ra_bp, ha_bp, insights_bp, live_bp, cm_bp, rollover_bp, menu_bp, hw_bp, wp_bp]:
    app.register_blueprint(bp)

# ── Year group session context ─────────────────────────────────────────────────
from flask import session, request as _req, redirect as _redirect
from data_manager import YEAR_GROUP_CLASSES as _YGC


# ── Public landing page ────────────────────────────────────────────────────────
from flask import session as _session, redirect as _redir, url_for as _url_for
from flask import render_template as _render

@app.route('/')
def index():
    if _session.get('authenticated'):
        return _redir(_url_for('dash.dashboard'))
    return _render('landing.html')

@app.route('/set-year/<yr>')
def set_year(yr):
    """Persist the active year group in session and redirect back."""
    if yr in _YGC:
        session['year_group'] = yr
    return _redirect(_req.referrer or '/')

@app.context_processor
def inject_year():
    yr = session.get('year_group', '4')
    return {'active_year': yr, 'all_year_groups': list(_YGC.keys())}

if __name__ == '__main__':
    app.run(debug=True)
