# app.py — точка входа, инициализация Flask и БД
import os

from flask import Flask, flash, redirect, render_template, request, url_for

from models import ReportSettings, db
from routes.athletes import bp as athletes_bp
from routes.import_export import bp as import_export_bp
from routes.reports import bp as reports_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "athletes.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.jinja_env.finalize = lambda value: "" if value is None else value

    db.init_app(app)
    app.register_blueprint(athletes_bp)
    app.register_blueprint(import_export_bp)
    app.register_blueprint(reports_bp)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        return redirect(url_for("athletes.athletes_list"))

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        report_settings = ReportSettings.query.first()

        if request.method == "POST":
            if not report_settings:
                report_settings = ReportSettings()
                db.session.add(report_settings)
            report_settings.organization_name = request.form.get("organization_name", "").strip()
            report_settings.chairman_name = request.form.get("chairman_name", "").strip()
            report_settings.head_coach_name = request.form.get("head_coach_name", "").strip()
            report_settings.sport_name = request.form.get("sport_name", "").strip()
            year_raw = request.form.get("year", "").strip()
            report_settings.year = int(year_raw) if year_raw.isdigit() else None
            db.session.commit()
            flash("Настройки сохранены", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html", settings=report_settings)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
