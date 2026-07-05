# app.py — точка входа, инициализация Flask и БД
import os

from flask import Flask, redirect, url_for

from models import db
from routes.athletes import bp as athletes_bp
from routes.import_export import bp as import_export_bp
from routes.reports import bp as reports_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "athletes.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    app.register_blueprint(athletes_bp)
    app.register_blueprint(import_export_bp)
    app.register_blueprint(reports_bp)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        return redirect(url_for("athletes.athletes_list"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
