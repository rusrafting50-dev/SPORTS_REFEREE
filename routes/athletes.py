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
# (путь, подпись кнопки, эндпоинт, паттерн дисциплины)
ROUTE_TYPES = [
    ("/routes/ski", "Маршрут - лыжный (1 - 6 категория)", "athletes.athletes_routes_ski", r"(?is)маршрут.*лыжн.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)"),
    ("/routes/hiking", "Маршрут - пешеходный (1 - 6 категория)", "athletes.athletes_routes_hiking", r"(?is)маршрут.*пешеход.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)"),
    ("/routes/mountain", "Маршрут - горный (1 - 6 категория)", "athletes.athletes_routes_mountain", r"(?is)маршрут.*горн.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)"),
    ("/routes/water", "Маршрут - водный (1 - 6 категория)", "athletes.athletes_routes_water", r"(?is)маршрут.*водн.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)"),
    ("/routes/vehicle", "Маршрут – на средствах передвижения (1 - 6 категория)", "athletes.athletes_routes_vehicle", r"(?is)маршрут.*средствах передвижения.*\(\s*\d+\s*-\s*\d+\s*категория\s*\)"),
]

# Конкретные виды дистанций для кнопок на странице /athletes/distances:
# (путь, подпись кнопки, эндпоинт, паттерн дисциплины)
DISTANCE_TYPES = [
    ("/distances/hiking", "Дистанции пешеходные", "athletes.athletes_distances_hiking", r"(?is)дистанц.*пешеход"),
    ("/distances/ski", "Дистанции лыжные", "athletes.athletes_distances_ski", r"(?is)дистанц.*лыжн"),
    ("/distances/mountain", "Дистанции горные", "athletes.athletes_distances_mountain", r"(?is)дистанц.*горн"),
    ("/distances/water", "Дистанции водные", "athletes.athletes_distances_water", r"(?is)дистанц.*водн"),
    ("/distances/vehicle-bike", "Дистанции на средствах передвижения (вело)", "athletes.athletes_distances_vehicle_bike", r"(?is)дистанц.*средствах передвижения.*вело"),
    ("/distances/vehicle-horse", "Дистанции на средствах передвижения (конные)", "athletes.athletes_distances_vehicle_horse", r"(?is)дистанц.*средствах передвижения.*конн"),
]


def _apply_common_filters(query):
    discipline = request.args.get("discipline", "")
    gender = request.args.get("gender", "")
    rank = request.args.get("rank", "")
    territory = request.args.get("territory", "")
    category = request.args.get("category", "")

    if discipline:
        query = query.filter(Athlete.discipline.contains(discipline))
    if gender:
        query = query.filter(Athlete.gender == gender)
    if rank:
        query = query.filter(Athlete.rank == rank)
    if territory:
        query = query.filter(Athlete.territory == territory)
    if category:
        query = query.filter(Athlete.category == category)

    filters = {
        "discipline": discipline,
        "gender": gender,
        "rank": rank,
        "territory": territory,
        "category": category,
    }
    return query, filters


def _render_athletes_list(query, **extra_context):
    query, filters = _apply_common_filters(query)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Athlete.last_name).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template(
        "athletes/list.html",
        athletes=pagination.items,
        pagination=pagination,
        filters=filters,
        references=references,
        **extra_context,
    )


@bp.route("/")
def athletes_list():
    query = Athlete.query.filter_by(is_active=True)
    return _render_athletes_list(query)


@bp.route("/routes")
def athletes_routes_list():
    query = Athlete.query.filter_by(is_active=True).filter(
        Athlete.discipline.op("REGEXP")(ROUTE_DISCIPLINE_PATTERN)
    )
    return _render_athletes_list(query, list_buttons=ROUTE_TYPES)


@bp.route("/distances")
def athletes_distances_list():
    query = Athlete.query.filter_by(is_active=True).filter(
        Athlete.discipline.op("REGEXP")(DISTANCE_DISCIPLINE_PATTERN)
    )
    return _render_athletes_list(query, list_buttons=DISTANCE_TYPES)


def _make_discipline_type_view(pattern):
    def view():
        query = Athlete.query.filter_by(is_active=True).filter(
            Athlete.discipline.op("REGEXP")(pattern)
        )
        return _render_athletes_list(query)
    return view


for _path, _label, _endpoint, _pattern in ROUTE_TYPES + DISTANCE_TYPES:
    bp.add_url_rule(
        _path,
        endpoint=_endpoint.split(".")[1],
        view_func=_make_discipline_type_view(_pattern),
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

    return render_template("athletes/form.html", athlete=None, references=references)


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
