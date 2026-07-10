# routes/reports.py — формирование и предпросмотр отчётов
from datetime import datetime
from io import BytesIO

from flask import Blueprint, render_template, request, send_file

import references
from excel_generator import generate_changes_report, generate_report
from models import Athlete, ChangeLog, ReportSettings, db

bp = Blueprint("reports", __name__, url_prefix="/reports")


def get_settings():
    return ReportSettings.query.first()


def apply_filters(query, args):
    discipline = args.get("discipline", "")
    age_category = args.get("age_category", "")
    territory = args.get("territory", "")
    gender = args.get("gender", "")
    only_national_team = args.get("only_national_team") == "on"

    if discipline:
        query = query.filter(Athlete.discipline == discipline)
    if age_category:
        query = query.filter(Athlete.age_category == age_category)
    if territory:
        query = query.filter(Athlete.territory == territory)
    if gender:
        query = query.filter(Athlete.gender == gender)
    if only_national_team:
        query = query.filter(Athlete.national_team.isnot(None), Athlete.national_team != "")

    return query


def get_doc_date(args):
    doc_date_raw = args.get("doc_date", "")
    if doc_date_raw:
        return datetime.strptime(doc_date_raw, "%Y-%m-%d").date()
    return datetime.today().date()


def _athlete_ids_active_as_of(doc_date):
    """ID спортсменов, состоявших в сборной на указанную дату — по истории «Членство в сборной
    команде» (как и в выгрузке «Изменения в список»). Для спортсменов без единой записи истории
    (например, добавленных обычным импортом основного списка) используется их текущий статус
    is_active, чтобы такие данные не пропадали из отчёта."""
    logs = (
        ChangeLog.query
        .filter(ChangeLog.change_date <= doc_date)
        .order_by(ChangeLog.change_date, ChangeLog.id)
        .all()
    )
    status_as_of = {}
    for log in logs:
        status_as_of[log.athlete_id] = log.change_type
    included_ids = {aid for aid, status in status_as_of.items() if status == "включён"}

    history_athlete_ids = {aid for (aid,) in db.session.query(ChangeLog.athlete_id).distinct()}
    no_history_active = (
        db.session.query(Athlete.id)
        .filter(Athlete.is_active.is_(True), ~Athlete.id.in_(history_athlete_ids))
        .all()
    )
    included_ids.update(aid for (aid,) in no_history_active)

    return included_ids


def get_filtered_athletes(args):
    doc_date = get_doc_date(args)
    athlete_ids = _athlete_ids_active_as_of(doc_date)
    if not athlete_ids:
        return []
    query = Athlete.query.filter(Athlete.id.in_(athlete_ids))
    query = apply_filters(query, args)
    return query.order_by(Athlete.last_name).all()


def get_selected_filters(args):
    return {
        "discipline": args.get("discipline", ""),
        "age_category": args.get("age_category", ""),
        "territory": args.get("territory", ""),
        "gender": args.get("gender", ""),
        "only_national_team": args.get("only_national_team") == "on",
        "doc_date": args.get("doc_date", "") or datetime.today().date().isoformat(),
    }


def get_changes_lists(args):
    doc_date_raw = args.get("doc_date", "")
    doc_date = datetime.strptime(doc_date_raw, "%Y-%m-%d").date() if doc_date_raw else datetime.today().date()
    doc_number = args.get("document_number", "").strip()

    query = ChangeLog.query.filter(ChangeLog.change_date == doc_date)
    if doc_number:
        query = query.filter(ChangeLog.document_number == doc_number)
    logs = query.all()

    exclude_ids = [log.athlete_id for log in logs if log.change_type == "исключён"]
    include_ids = [log.athlete_id for log in logs if log.change_type == "включён"]

    exclude_list = (
        Athlete.query.filter(Athlete.id.in_(exclude_ids)).order_by(Athlete.last_name).all()
        if exclude_ids else []
    )
    include_list = (
        Athlete.query.filter(Athlete.id.in_(include_ids)).order_by(Athlete.last_name).all()
        if include_ids else []
    )
    return exclude_list, include_list, doc_date, doc_number


@bp.route("")
def reports_filter():
    return render_template(
        "reports/filter.html",
        references=references,
        today=datetime.today().date().isoformat(),
    )


@bp.route("/preview", methods=["POST"])
def reports_preview():
    athletes = get_filtered_athletes(request.form)
    filters = get_selected_filters(request.form)
    return render_template("reports/preview.html", athletes=athletes, filters=filters)


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


@bp.route("/changes/preview", methods=["POST"])
def reports_changes_preview():
    exclude_list, include_list, doc_date, doc_number = get_changes_lists(request.form)
    return render_template(
        "reports/changes_preview.html",
        exclude_list=exclude_list, include_list=include_list,
        doc_date=doc_date.isoformat(), document_number=doc_number,
    )


@bp.route("/changes/export", methods=["POST"])
def reports_changes_export():
    exclude_list, include_list, doc_date, doc_number = get_changes_lists(request.form)
    settings = get_settings()

    wb = generate_changes_report(exclude_list, include_list, settings, doc_date, doc_number)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    suffix = doc_number or doc_date.isoformat()
    filename = f"Изменения_списка_в_сборную_МО_спортивный_туризм_{suffix}.xlsx"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
