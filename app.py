# app.py — точка входа, инициализация Flask и БД
import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape
from sqlalchemy import inspect, text

import references
from models import LocalBranch, Settings, Subject, db
from routes.api import bp as api_bp
from routes.judges import bp as judges_bp
from routes.seminars import bp as seminars_bp
from subjects import (
    обеспечить_субъекты_цфо, местные_отделения_субъекта, текущее_местное_отделение,
    текущее_местное_отделение_id, текущий_субъект, текущий_субъект_id, убрать_лишние_субъекты_цфо,
)

# override=True — .env должен побеждать даже если такая переменная уже
# случайно задана на уровне Windows (иначе пустое/старое системное
# значение молча маскирует правильное значение из .env).
load_dotenv(override=True)

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


_SEMINAR_CATEGORY_BADGE = {
    "Всероссийская": "bg-danger",
    "Первая": "bg-warning text-dark",
    "Вторая": "bg-info text-dark",
    "Третья": "bg-secondary",
    "Юный судья": "bg-success",
}


def seminar_category_badge(value):
    """Категория семинара -> класс цветного бейджа Bootstrap."""
    return _SEMINAR_CATEGORY_BADGE.get(value, "bg-secondary")


def seminar_category_abbr(value):
    """Присваиваемая (подтверждаемая) категория семинара -> сокращение (ССВК/СС1К/...) для протокола."""
    return references.SEMINAR_CATEGORY_ABBREVIATIONS.get(value, value)


def _is_initial(token):
    return len(token) <= 2 and token.endswith(".")


def initials_first(full_name):
    """«Милевский Е. В.» -> «Е. В. Милевский» (инициалы вперёд) для подписи в протоколе семинара."""
    if not full_name:
        return full_name
    parts = full_name.split()
    initials = [p for p in parts if _is_initial(p)]
    rest = [p for p in parts if not _is_initial(p)]
    if not initials or not rest:
        return full_name
    return " ".join(initials) + " " + " ".join(rest)


def ru_plural(n, one, few, many):
    """Склонение существительного по числу n (1 заявка / 2 заявки / 5 заявок)."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


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
    app.jinja_env.filters["seminar_category_badge"] = seminar_category_badge
    app.jinja_env.filters["seminar_category_abbr"] = seminar_category_abbr
    app.jinja_env.filters["initials_first"] = initials_first
    app.jinja_env.filters["ru_plural"] = ru_plural

    db.init_app(app)
    app.register_blueprint(judges_bp)
    app.register_blueprint(seminars_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()
        _sync_missing_columns()
        обеспечить_субъекты_цфо()
        убрать_лишние_субъекты_цфо()

    @app.context_processor
    def inject_subjects():
        subject_id = текущий_субъект_id()
        return {
            "all_subjects": Subject.query.order_by(Subject.name).all(),
            "current_subject": текущий_субъект(),
            "current_subject_local_branches": местные_отделения_субъекта(subject_id),
            "current_local_branch": текущее_местное_отделение(),
        }

    @app.route("/")
    def index():
        return redirect(url_for("seminars.seminars_list"))

    @app.route("/subjects/<int:subject_id>/switch")
    def subjects_switch(subject_id):
        Subject.query.get_or_404(subject_id)
        session["judge_subject_id"] = subject_id
        session.pop("judge_local_branch_id", None)  # отделение прошлого субъекта здесь больше не действует
        # Всегда на список судей, а не на request.referrer: пункт в шапке доступен
        # с любой страницы (например, «Семинары»), и клик должен сразу показать
        # таблицу судей этого субъекта, а не молча отфильтровать и остаться на месте.
        return redirect(url_for("judges.judges_list"))

    @app.route("/subjects/clear")
    def subjects_clear():
        session.pop("judge_subject_id", None)
        session.pop("judge_local_branch_id", None)
        return redirect(url_for("judges.judges_list"))

    # Добавление/переименование/удаление субъектов и местных отделений —
    # только со страницы «Настройки» (settings()); в шапке эти справочники
    # только для переключения (subjects_switch/clear, local_branches_switch/clear выше).

    @app.route("/subjects", methods=["POST"])
    def subjects_add():
        name = request.form.get("name", "").strip()
        if not name:
            flash("Укажите наименование субъекта Российской Федерации", "error")
            return redirect(url_for("settings"))
        if Subject.query.filter_by(name=name).first():
            flash("Такой субъект уже есть в списке", "warning")
        else:
            db.session.add(Subject(name=name))
            db.session.commit()
            flash(f"Субъект «{name}» добавлен", "success")
        return redirect(url_for("settings"))

    @app.route("/subjects/<int:subject_id>/edit", methods=["POST"])
    def subjects_edit(subject_id):
        subject = Subject.query.get_or_404(subject_id)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Укажите наименование субъекта Российской Федерации", "error")
            return redirect(url_for("settings"))
        if Subject.query.filter(Subject.name == name, Subject.id != subject_id).first():
            flash("Субъект с таким наименованием уже есть в списке", "warning")
            return redirect(url_for("settings"))
        subject.name = name
        subject.organization_name = request.form.get("organization_name", "").strip()
        subject.organization_address = request.form.get("organization_address", "").strip()
        subject.organization_contacts = request.form.get("organization_contacts", "").strip()
        db.session.commit()
        flash(f"Субъект «{name}» сохранён", "success")
        return redirect(url_for("settings"))

    @app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
    def subjects_delete(subject_id):
        subject = Subject.query.get_or_404(subject_id)
        if текущий_субъект_id() == subject_id:
            session.pop("judge_subject_id", None)
            session.pop("judge_local_branch_id", None)
        db.session.delete(subject)  # каскадно удаляет и местные отделения этого субъекта
        db.session.commit()
        flash(f"Субъект «{subject.name}» удалён", "success")
        return redirect(url_for("settings"))

    @app.route("/local-branches/<int:branch_id>/switch")
    def local_branches_switch(branch_id):
        LocalBranch.query.get_or_404(branch_id)
        session["judge_local_branch_id"] = branch_id
        return redirect(url_for("judges.judges_list"))

    @app.route("/local-branches/clear")
    def local_branches_clear():
        session.pop("judge_local_branch_id", None)
        return redirect(url_for("judges.judges_list"))

    @app.route("/local-branches", methods=["POST"])
    def local_branches_add():
        subject = Subject.query.get(request.form.get("subject_id", type=int))
        if not subject:
            flash("Укажите субъект Российской Федерации", "error")
            return redirect(url_for("settings"))
        name = request.form.get("name", "").strip()
        if not name:
            flash("Укажите наименование муниципального образования", "error")
            return redirect(url_for("settings"))
        if LocalBranch.query.filter_by(subject_id=subject.id, name=name).first():
            flash("Такое местное отделение уже есть в списке", "warning")
        else:
            db.session.add(LocalBranch(subject_id=subject.id, name=name))
            db.session.commit()
            flash(f"Местное отделение «{name}» добавлено", "success")
        return redirect(url_for("settings"))

    @app.route("/local-branches/<int:branch_id>/edit", methods=["POST"])
    def local_branches_edit(branch_id):
        branch = LocalBranch.query.get_or_404(branch_id)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Укажите наименование муниципального образования", "error")
            return redirect(url_for("settings"))
        existing = LocalBranch.query.filter(
            LocalBranch.subject_id == branch.subject_id, LocalBranch.name == name, LocalBranch.id != branch_id,
        ).first()
        if existing:
            flash("Такое местное отделение уже есть в списке", "warning")
            return redirect(url_for("settings"))
        branch.name = name
        db.session.commit()
        flash(f"Местное отделение переименовано в «{name}»", "success")
        return redirect(url_for("settings"))

    @app.route("/local-branches/<int:branch_id>/delete", methods=["POST"])
    def local_branches_delete(branch_id):
        branch = LocalBranch.query.get_or_404(branch_id)
        if текущее_местное_отделение_id() == branch_id:
            session.pop("judge_local_branch_id", None)
        db.session.delete(branch)
        db.session.commit()
        flash(f"Местное отделение «{branch.name}» удалено", "success")
        return redirect(url_for("settings"))

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        org_settings = Settings.query.first()

        if request.method == "POST":
            if not org_settings:
                org_settings = Settings()
                db.session.add(org_settings)
            org_settings.sport_name = request.form.get("sport_name", "").strip()
            org_settings.sport_code = request.form.get("sport_code", "").strip()
            db.session.commit()
            flash("Настройки сохранены", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html", settings=org_settings)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5005)
