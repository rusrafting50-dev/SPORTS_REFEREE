# routes/athletes.py — CRUD спортсменов
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

import references
from models import Athlete, ChangeLog, db

bp = Blueprint("athletes", __name__, url_prefix="/athletes")

PER_PAGE = 20

# Маршрут (Маршрут - лыжный, водный, горный и т.д. "N-N категория") — независимо от пробелов/дефиса
ROUTE_DISCIPLINE_PATTERN = r"\(\s*\d+\s*-\s*\d+\s*категория\s*\)"

# Дистанции / Дистанция / Группа дисциплин "дистанция" — без учёта регистра
DISTANCE_DISCIPLINE_PATTERN = r"(?i)дистанц"

# Конкретные виды маршрутов для кнопок на странице /athletes/routes:
# (путь, подпись кнопки, эндпоинт, паттерн дисциплины, заголовок страницы, дисциплина для предзаполнения при добавлении)
ROUTE_TYPES = [
    ("/routes/ski", "Маршрут - лыжный (1 - 6 категория)", "athletes.athletes_routes_ski", r"(?is)маршрут.*лыжн.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)", "Маршрут - лыжный (1-6 категория)", "Маршрут - лыжный (1-6 категория)"),
    ("/routes/hiking", "Маршрут - пешеходный (1 - 6 категория)", "athletes.athletes_routes_hiking", r"(?is)маршрут.*пешеход.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)", "Маршрут - пешеходный (1-6 категория)", "Маршрут - пешеходный (1-6 категория)"),
    ("/routes/mountain", "Маршрут - горный (1 - 6 категория)", "athletes.athletes_routes_mountain", r"(?is)маршрут.*горн.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)", "Маршрут - горный (1-6 категория)", "Маршрут - горный (1-6 категория)"),
    ("/routes/water", "Маршрут - водный (1 - 6 категория)", "athletes.athletes_routes_water", r"(?is)маршрут.*водн.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)", None, None),
    ("/routes/vehicle", "Маршрут – на средствах передвижения (1 - 6 категория)", "athletes.athletes_routes_vehicle", r"(?is)маршрут.*средствах передвижения.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)", "Маршрут - на средствах передвижения (1-6 категория)", "Маршрут - на средствах передвижения (1-6 категория)"),
]

# Конкретные виды дистанций для кнопок на странице /athletes/distances:
# (путь, подпись кнопки, эндпоинт, паттерн дисциплины, заголовок страницы, дисциплина для предзаполнения при добавлении)
DISTANCE_TYPES = [
    ("/distances/hiking", "Дистанции пешеходные", "athletes.athletes_distances_hiking", r"(?is)дистанц.*пешеход", None, None),
    ("/distances/ski", "Дистанции лыжные", "athletes.athletes_distances_ski", r"(?is)дистанц.*лыжн", None, None),
    ("/distances/mountain", "Дистанции горные", "athletes.athletes_distances_mountain", r"(?is)дистанц.*горн", None, None),
    ("/distances/water", "Дистанции водные", "athletes.athletes_distances_water", r"(?is)дистанц.*водн", None, None),
    ("/distances/vehicle-bike", "Дистанции на средствах передвижения (вело)", "athletes.athletes_distances_vehicle_bike", r"(?is)дистанц.*средствах передвижения.*вело", None, None),
    ("/distances/vehicle-horse", "Дистанции на средствах передвижения (конные)", "athletes.athletes_distances_vehicle_horse", r"(?is)дистанц.*средствах передвижения.*конн", None, None),
]


def _apply_common_filters(query):
    discipline = request.args.get("discipline", "")
    age_category = request.args.get("age_category", "")
    gender = request.args.get("gender", "")
    territory = request.args.get("territory", "")
    organization = request.args.get("organization", "")

    if discipline:
        query = query.filter(Athlete.discipline.contains(discipline))
    if age_category:
        query = query.filter(Athlete.age_category == age_category)
    if gender:
        query = query.filter(Athlete.gender == gender)
    if territory:
        query = query.filter(Athlete.territory == territory)
    if organization:
        query = query.filter(Athlete.organization.contains(organization))

    filters = {
        "discipline": discipline,
        "age_category": age_category,
        "gender": gender,
        "territory": territory,
        "organization": organization,
    }
    return query, filters


def _render_athletes_list(query, heading="Спортсмены", show_add_button=True, discipline_preset=None, **extra_context):
    query, filters = _apply_common_filters(query)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Athlete.last_name).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template(
        "athletes/list.html",
        athletes=pagination.items,
        pagination=pagination,
        filters=filters,
        references=references,
        heading=heading,
        show_add_button=show_add_button,
        discipline_preset=discipline_preset,
        **extra_context,
    )


@bp.route("/")
def athletes_list():
    query = Athlete.query.filter_by(is_active=True)
    return _render_athletes_list(query, heading="Список сборной команды")


@bp.route("/routes")
def athletes_routes_list():
    query = Athlete.query.filter_by(is_active=True).filter(
        Athlete.discipline.op("REGEXP")(ROUTE_DISCIPLINE_PATTERN)
    )
    return _render_athletes_list(
        query, list_buttons=ROUTE_TYPES,
        heading="Группа дисциплин МАРШРУТ", show_add_button=False,
    )


@bp.route("/distances")
def athletes_distances_list():
    query = Athlete.query.filter_by(is_active=True).filter(
        Athlete.discipline.op("REGEXP")(DISTANCE_DISCIPLINE_PATTERN)
    )
    return _render_athletes_list(
        query, list_buttons=DISTANCE_TYPES,
        heading="Группа дисциплин ДИСТАНЦИЯ", show_add_button=False,
    )


def _make_discipline_type_view(pattern, heading, discipline_preset):
    def view():
        query = Athlete.query.filter_by(is_active=True).filter(
            Athlete.discipline.op("REGEXP")(pattern)
        )
        kwargs = {}
        if heading:
            kwargs["heading"] = heading
        if discipline_preset:
            kwargs["discipline_preset"] = discipline_preset
        return _render_athletes_list(query, **kwargs)
    return view


for _path, _label, _endpoint, _pattern, _heading, _discipline_preset in ROUTE_TYPES + DISTANCE_TYPES:
    bp.add_url_rule(
        _path,
        endpoint=_endpoint.split(".")[1],
        view_func=_make_discipline_type_view(_pattern, _heading, _discipline_preset),
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

    preset_discipline = request.args.get("discipline", "")
    return render_template(
        "athletes/form.html", athlete=None, references=references, preset_discipline=preset_discipline
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

    return render_template("athletes/form.html", athlete=athlete, references=references)


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
    athlete.is_active = True
    db.session.add(
        ChangeLog(athlete_id=athlete.id, change_type="включён", change_date=date.today())
    )
    db.session.commit()
    flash("Спортсмен возвращён в список", "success")
    return redirect(url_for("athletes.athletes_detail", athlete_id=athlete.id))


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
