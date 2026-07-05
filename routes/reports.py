# routes/reports.py — формирование и предпросмотр отчётов
from datetime import datetime
from io import BytesIO

from flask import Blueprint, request, send_file

from excel_generator import generate_report
from models import Athlete, ReportSettings

bp = Blueprint("reports", __name__, url_prefix="/reports")


def get_settings():
    return ReportSettings.query.first()


def apply_filters(query, args):
    disciplines = args.getlist("discipline")
    age_categories = args.getlist("age_category")
    ranks = args.getlist("rank")
    territories = args.getlist("territory")
    gender = args.get("gender", "")
    category = args.get("category", "")
    only_national_team = args.get("only_national_team") == "on"

    if disciplines:
        query = query.filter(Athlete.discipline.in_(disciplines))
    if age_categories:
        query = query.filter(Athlete.age_category.in_(age_categories))
    if ranks:
        query = query.filter(Athlete.rank.in_(ranks))
    if territories:
        query = query.filter(Athlete.territory.in_(territories))
    if gender:
        query = query.filter(Athlete.gender == gender)
    if category:
        query = query.filter(Athlete.category == category)
    if only_national_team:
        query = query.filter(Athlete.national_team.isnot(None), Athlete.national_team != "")

    return query


def get_filtered_athletes(args):
    query = Athlete.query.filter_by(is_active=True)
    query = apply_filters(query, args)
    return query.order_by(Athlete.last_name).all()


def get_doc_date(args):
    doc_date_raw = args.get("doc_date", "")
    if doc_date_raw:
        return datetime.strptime(doc_date_raw, "%Y-%m-%d").date()
    return datetime.today().date()


@bp.route("/export", methods=["POST"])
def reports_export():
    athletes = get_filtered_athletes(request.form)
    settings = get_settings()
    doc_date = get_doc_date(request.form)

    wb = generate_report(athletes, settings, doc_date)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    year = settings.year if settings else doc_date.year
    filename = f"Список_МО_спортивный_туризм_{year}_{doc_date.isoformat()}.xlsx"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
