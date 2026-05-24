import os
from flask import Flask

app = Flask(__name__)
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

for bp in [auth_bp, dash_bp, tt_bp, bee_bp, learners_bp, hl_bp, settings_bp, rules_bp, stubs_bp, print_bp, wa_bp, ra_bp, ha_bp, insights_bp, live_bp, cm_bp]:
    app.register_blueprint(bp)

if __name__ == '__main__':
    app.run(debug=True)
