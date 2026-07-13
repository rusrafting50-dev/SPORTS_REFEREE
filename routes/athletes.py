# routes/athletes.py — CRUD спортсменов
import re
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

import references
from models import Athlete, ChangeLog, db

bp = Blueprint("athletes", __name__, url_prefix="/athletes")

PER_PAGE = 20

# Варианты поля "Спортивная дисциплина или группа дисциплин" в формах
# добавления/редактирования спортсмена и тренера
DISCIPLINE_SELECT_OPTIONS = ["Все дисциплины", "Группа дисциплин R4", "Группа дисциплин R6"]

# Кнопки на странице / ("Список сборной команды") — по группам возрастных категорий
TEAM_AGE_CATEGORY_TYPES = [
    ("/team/men-women", "ССВК", "athletes.athletes_team_men_women", ["Мужчины", "Женщины"], "Мужчины, женщины"),
    ("/team/juniors", "СС1К", "athletes.athletes_team_juniors", ["Юниоры", "Юниорки"], "Юниоры, юниорки"),
    ("/team/youth", "СС2К и СС3К", "athletes.athletes_team_youth", ["Юноши", "Девушки"], "Юноши, девушки"),
]

# Тренер / Главный тренер / тренер — без учёта регистра
TRAINER_CATEGORY_PATTERN = r"(?i)тренер"

# Варианты категории для формы добавления тренера
TRAINER_CATEGORY_OPTIONS = ["Главный тренер", "Тренер", "Специалист"]

# Категория для формы добавления спортсмена
ATHLETE_CATEGORY_OPTIONS = ["Спортсмен"]

# Варианты возрастной категории для формы добавления тренера
TRAINER_AGE_CATEGORY_OPTIONS = [
    "Все возрастные категории",
    "Мужчины",
    "Женщины",
    "Мужчины, женщины",
    "Мужчины, юниоры",
    "Женщины, юниорки",
    "Юниоры",
    "Юниорки",
    "Юниоры, юниорки",
    "Юноши",
    "Девушки",
    "Юноши, девушки",
]


def _apply_common_filters(query):
    age_category = request.args.get("age_category", "")
    territory = request.args.get("territory", "")
    organization = request.args.get("organization", "")

    if age_category:
        query = query.filter(Athlete.age_category == age_category)
    if territory:
        query = query.filter(Athlete.territory == territory)
    if organization:
        query = query.filter(Athlete.organization == organization)

    filters = {
        "age_category": age_category,
        "territory": territory,
        "organization": organization,
    }
    return query, filters


def _with_current_value(options, current_value):
    """Список options, дополненный current_value, если его там ещё нет (чтобы не потерять при сохранении)."""
    if current_value and current_value not in options:
        return options + [current_value]
    return options


def _distinct_organizations():
    rows = (
        db.session.query(Athlete.organization)
        .filter(Athlete.organization.isnot(None), Athlete.organization != "")
        .distinct()
        .order_by(Athlete.organization)
        .all()
    )
    return [row[0] for row in rows]


def _render_athletes_list(
    query, heading="Спортсмены", show_add_button=True, discipline_preset=None,
    link_fio_to_new=False, link_fio_to_edit=False, discipline_group=None,
    add_button_label="Добавить спортсмена", add_form_variant=None, age_category_filter_options=None,
    highlight_active=True, **extra_context,
):
    query, filters = _apply_common_filters(query)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Athlete.last_name).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template(
        "athletes/list.html",
        athletes=pagination.items,
        pagination=pagination,
        filters=filters,
        references=references,
        organizations=_distinct_organizations(),
        heading=heading,
        show_add_button=show_add_button,
        discipline_preset=discipline_preset,
        link_fio_to_new=link_fio_to_new,
        link_fio_to_edit=link_fio_to_edit,
        age_category_filter_options=age_category_filter_options or references.AGE_CATEGORIES,
        discipline_group=discipline_group,
        add_button_label=add_button_label,
        add_form_variant=add_form_variant,
        highlight_active=highlight_active,
        **extra_context,
    )


@bp.route("/")
def athletes_list():
    query = Athlete.query.filter_by(is_active=True)
    list_buttons = TEAM_AGE_CATEGORY_TYPES + [
        ("", "Тренеры", "athletes.athletes_trainers_list", [], "Тренеры"),
    ]
    return _render_athletes_list(
        query, list_buttons=list_buttons,
        heading="Список спортивных судей",
        show_add_button=False, highlight_active=False,
    )


@bp.route("/trainers")
def athletes_trainers_list():
    query = Athlete.query.filter(
        Athlete.category.op("REGEXP")(TRAINER_CATEGORY_PATTERN)
    )
    return _render_athletes_list(
        query, heading="Тренеры",
        add_button_label="Добавить тренера", add_form_variant="trainer",
        age_category_filter_options=TRAINER_AGE_CATEGORY_OPTIONS,
    )


def _make_age_category_view(age_categories, heading):
    def view():
        query = Athlete.query.filter(Athlete.age_category.in_(age_categories))
        return _render_athletes_list(
            query, heading=heading, show_add_button=False,
            age_category_filter_options=age_categories,
            highlight_active=True,
        )
    return view


for _path, _label, _endpoint, _age_categories, _heading in TEAM_AGE_CATEGORY_TYPES:
    bp.add_url_rule(
        _path,
        endpoint=_endpoint.split(".")[1],
        view_func=_make_age_category_view(_age_categories, _heading),
    )


@bp.route("/new", methods=["GET", "POST"])
def athletes_new():
    if request.method == "POST":
        athlete = Athlete()
        _fill_athlete_from_form(athlete, request.form)
        db.session.add(athlete)
        db.session.commit()
        flash("Спортсмен добавлен", "success")
        return redirect(url_for("athletes.athletes_detail", athlete_id=athlete.id))

    discipline_options = DISCIPLINE_SELECT_OPTIONS
    if request.args.get("form_variant") == "trainer":
        category_options = TRAINER_CATEGORY_OPTIONS
        age_category_options = TRAINER_AGE_CATEGORY_OPTIONS
        entity_label = "тренера"
    else:
        category_options = ATHLETE_CATEGORY_OPTIONS
        age_category_options = None
        entity_label = "спортсмена"

    preset_discipline = request.args.get("discipline", "")
    if discipline_options and not preset_discipline:
        preset_discipline = discipline_options[0]

    return render_template(
        "athletes/form.html", athlete=None, references=references,
        preset_discipline=preset_discipline, discipline_options=discipline_options,
        category_options=category_options, age_category_options=age_category_options,
        entity_label=entity_label,
    )


@bp.route("/<int:athlete_id>")
def athletes_detail(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)
    return render_template("athletes/detail.html", athlete=athlete)


@bp.route("/<int:athlete_id>/edit", methods=["GET", "POST"])
def athletes_edit(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)

    if request.method == "POST":
        _fill_athlete_from_form(athlete, request.form)
        db.session.commit()
        flash("Изменения сохранены", "success")
        return redirect(url_for("athletes.athletes_detail", athlete_id=athlete.id))

    is_trainer = bool(athlete.category and re.search(TRAINER_CATEGORY_PATTERN, athlete.category))
    if is_trainer:
        # Текущее значение спортсмена может не совпадать буквально ни с одним
        # из готовых вариантов (регистр, кавычки и т.п.) — добавляем его в список,
        # чтобы оно корректно подставлялось и не терялось при сохранении без изменений.
        category_options = _with_current_value(TRAINER_CATEGORY_OPTIONS, athlete.category)
        age_category_options = _with_current_value(TRAINER_AGE_CATEGORY_OPTIONS, athlete.age_category)
        entity_label = "тренера"
    else:
        category_options = None
        age_category_options = None
        entity_label = "спортсмена"
    discipline_options = _with_current_value(DISCIPLINE_SELECT_OPTIONS, athlete.discipline)

    return render_template(
        "athletes/form.html", athlete=athlete, references=references,
        category_options=category_options, age_category_options=age_category_options,
        discipline_options=discipline_options, entity_label=entity_label,
    )


@bp.route("/<int:athlete_id>/deactivate", methods=["POST"])
def athletes_deactivate(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)
    athlete.is_active = False
    db.session.add(
        ChangeLog(athlete_id=athlete.id, change_type="исключён", change_date=date.today())
    )
    db.session.commit()
    flash("Спортсмен исключён из списка", "success")
    return redirect(url_for("athletes.athletes_detail", athlete_id=athlete.id))


@bp.route("/<int:athlete_id>/activate", methods=["POST"])
def athletes_activate(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)
    is_first_add = not athlete.change_logs
    athlete.is_active = True
    db.session.add(
        ChangeLog(athlete_id=athlete.id, change_type="включён", change_date=date.today())
    )
    db.session.commit()
    flash("Спортсмен добавлен в список" if is_first_add else "Спортсмен возвращён в список", "success")
    return redirect(url_for("athletes.athletes_detail", athlete_id=athlete.id))


@bp.route("/<int:athlete_id>/delete", methods=["POST"])
def athletes_delete(athlete_id):
    athlete = Athlete.query.get_or_404(athlete_id)
    is_trainer = bool(athlete.category and re.search(TRAINER_CATEGORY_PATTERN, athlete.category))
    db.session.delete(athlete)
    db.session.commit()
    flash("Тренер удалён" if is_trainer else "Спортсмен удалён", "success")
    return redirect(url_for("athletes.athletes_trainers_list" if is_trainer else "athletes.athletes_list"))


@bp.route("/change-logs/<int:log_id>/edit", methods=["POST"])
def change_log_edit(log_id):
    log = ChangeLog.query.get_or_404(log_id)
    date_raw = request.form.get("change_date", "").strip()
    if date_raw:
        try:
            log.change_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Некорректная дата", "error")
            return redirect(url_for("athletes.athletes_detail", athlete_id=log.athlete_id))
    log.document_number = request.form.get("document_number", "").strip() or None
    db.session.commit()
    flash("Запись о членстве в сборной команде обновлена", "success")
    return redirect(url_for("athletes.athletes_detail", athlete_id=log.athlete_id))


@bp.route("/change-logs/<int:log_id>/delete", methods=["POST"])
def change_log_delete(log_id):
    log = ChangeLog.query.get_or_404(log_id)
    athlete_id = log.athlete_id
    db.session.delete(log)
    db.session.commit()
    flash("Запись о членстве в сборной команде удалена", "success")
    return redirect(url_for("athletes.athletes_detail", athlete_id=athlete_id))


def _fill_athlete_from_form(athlete, form):
    athlete.last_name = form.get("last_name", "").strip()
    athlete.first_name = form.get("first_name", "").strip()
    athlete.middle_name = form.get("middle_name", "").strip() or None

    birth_date = form.get("birth_date", "")
    athlete.birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date() if birth_date else None

    athlete.gender = form.get("gender", "")
    athlete.discipline = form.get("discipline", "")
    athlete.category = form.get("category", "")
    athlete.age_category = form.get("age_category", "")
    athlete.rank = form.get("rank", "")
    athlete.organization = form.get("organization", "").strip()
    athlete.territory = form.get("territory", "")
    athlete.trainer = form.get("trainer", "").strip()
    athlete.result_regional = form.get("result_regional", "").strip()
    athlete.result_national = form.get("result_national", "").strip()
    athlete.result_international = form.get("result_international", "").strip()
    athlete.national_team = form.get("national_team", "").strip()
