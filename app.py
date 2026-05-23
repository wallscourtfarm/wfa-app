import os
from flask import Flask

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

from routes.auth         import auth_bp
from routes.dashboard    import dash_bp
from routes.tt           import tt_bp
from routes.bee          import bee_bp
from routes.learners     import learners_bp
from routes.home_learning import hl_bp
from routes.stubs        import stubs_bp

for bp in [auth_bp, dash_bp, tt_bp, bee_bp, learners_bp, hl_bp, stubs_bp]:
    app.register_blueprint(bp)

if __name__ == '__main__':
    app.run(debug=True)
