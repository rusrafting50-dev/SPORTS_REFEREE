# app.py — точка входа, инициализация Flask и БД
import os
import re

from flask import Flask, flash, redirect, render_template, request, url_for
from markupsafe import Markup, escape
from sqlalchemy import event
from sqlalchemy.engine import Engine

from models import ReportSettings, db
from routes.athletes import bp as athletes_bp
from routes.import_export import bp as import_export_bp
from routes.reports import bp as reports_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

CATEGORY_PATTERN = re.compile(r"\s*(\(\s*\d+\s*-\s*\d+\s*категория\s*\))", re.IGNORECASE)
TRAINER_SEPARATOR = re.compile(r",\s*")


def break_before_category(value):
    """Переносит '(N-N категория)' на новую строку независимо от исходных пробелов/переводов строк."""
    if not value:
        return value
    return Markup(CATEGORY_PATTERN.sub(r"<br>\1", str(escape(value))))


def break_trainers(value):
    """Каждого тренера (через запятую) — на отдельную строку, с запятой после инициалов."""
    if not value:
        return value
    parts = TRAINER_SEPARATOR.split(str(escape(value)))
    return Markup(",<br>".join(parts))


@event.listens_for(Engine, "connect")
def _register_sqlite_regexp(dbapi_connection, connection_record):
    """SQLite не поддерживает REGEXP без явной регистрации функции (нужно для фильтра "Маршруты")."""
    dbapi_connection.create_function(
        "REGEXP", 2, lambda pattern, value: value is not None and re.search(pattern, value) is not None
    )


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "athletes.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.jinja_env.finalize = lambda value: "" if value is None else value
    app.jinja_env.filters["break_before_category"] = break_before_category
    app.jinja_env.filters["break_trainers"] = break_trainers

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
