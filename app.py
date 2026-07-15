# app.py — точка входа, инициализация Flask и БД
import os

from flask import Flask, flash, redirect, render_template, request, url_for
from markupsafe import Markup, escape
from sqlalchemy import inspect, text

import references
from models import Settings, db
from routes.judges import bp as judges_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

_CATEGORY_TO_ABBR = {full: abbr for abbr, full in references.JUDGE_CATEGORY_ABBREVIATIONS.items()}


def break_after_comma(value):
    """После каждой запятой в тексте — перенос на новую строку."""
    if not value:
        return value
    return Markup(str(escape(value)).replace(",", ",<br>"))


def category_abbr(value):
    """Полное написание квалификационной категории судьи -> сокращение (ССВК/СС1К/...)."""
    return _CATEGORY_TO_ABBR.get(value, value)


def _sync_missing_columns():
    """Добавляет в уже существующую БД колонки, которых нет (db.create_all() таблицы не изменяет)."""
    inspector = inspect(db.engine)
    for table in db.metadata.tables.values():
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(db.engine.dialect)
            with db.engine.connect() as conn:
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))
                conn.commit()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "athletes.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.jinja_env.finalize = lambda value: "" if value is None else value
    app.jinja_env.filters["break_after_comma"] = break_after_comma
    app.jinja_env.filters["category_abbr"] = category_abbr

    db.init_app(app)
    app.register_blueprint(judges_bp)

    with app.app_context():
        db.create_all()
        _sync_missing_columns()

    @app.route("/")
    def index():
        return redirect(url_for("judges.judges_list"))

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        org_settings = Settings.query.first()

        if request.method == "POST":
            if not org_settings:
                org_settings = Settings()
                db.session.add(org_settings)
            org_settings.sport_name = request.form.get("sport_name", "").strip()
            org_settings.sport_code = request.form.get("sport_code", "").strip()
            org_settings.organization_name = request.form.get("organization_name", "").strip()
            org_settings.organization_address = request.form.get("organization_address", "").strip()
            org_settings.organization_contacts = request.form.get("organization_contacts", "").strip()
            db.session.commit()
            flash("Настройки сохранены", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html", settings=org_settings)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5002)
