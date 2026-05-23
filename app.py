import os
from flask import Flask, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

from routes.auth      import auth_bp
from routes.dashboard import dash_bp
from routes.tt        import tt_bp
from routes.bee       import bee_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dash_bp)
app.register_blueprint(tt_bp)
app.register_blueprint(bee_bp)

if __name__ == '__main__':
    app.run(debug=True)
