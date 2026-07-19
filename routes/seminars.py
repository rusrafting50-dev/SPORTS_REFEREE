# routes/seminars.py — семинары по подготовке спортивных судей по рафтингу
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

import references
from models import Seminar, SeminarApplication, SeminarApplicationParticipant, db

JUDGE_QUALIFICATIONS = ["ССВК", "СС1К", "СС2К", "СС3К"]

bp = Blueprint("seminars", __name__, url_prefix="/seminars")


def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _fill_seminar_from_form(seminar, form):
    seminar.name = form.get("name", "").strip() or None
    seminar.start_date = _parse_date(form.get("start_date"))
    seminar.period = form.get("period", "").strip() or None
    seminar.location = form.get("location", "").strip() or None
    seminar.category = form.get("category", "").strip() or None
    seminar.organizer = form.get("organizer", "").strip() or None
    seminar.program_hours = form.get("program_hours", "").strip() or None
    seminar.qualification_exam = form.get("qualification_exam", "").strip() or None
    seminar.leader_full_name = form.get("leader_full_name", "").strip() or None
    seminar.leader_category = form.get("leader_category", "").strip() or None
    seminar.leader_region = form.get("leader_region", "").strip() or None
    seminar.leader_phone = form.get("leader_phone", "").strip() or None


@bp.route("/")
def seminars_list():
    seminars = Seminar.query.order_by(Seminar.start_date.desc().nullslast(), Seminar.id.desc()).all()
    return render_template("seminars/list.html", featured=seminars[:3], rest=seminars[3:])


@bp.route("/new", methods=["GET", "POST"])
def seminars_new():
    if request.method == "POST":
        seminar = Seminar()
        _fill_seminar_from_form(seminar, request.form)
        db.session.add(seminar)
        db.session.commit()
        flash("Семинар добавлен", "success")
        return redirect(url_for("seminars.seminars_list"))
    return render_template("seminars/form.html", seminar=None, references=references)


@bp.route("/<int:seminar_id>")
def seminars_detail(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    return render_template("seminars/detail.html", seminar=seminar)


@bp.route("/<int:seminar_id>/edit", methods=["GET", "POST"])
def seminars_edit(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    if request.method == "POST":
        _fill_seminar_from_form(seminar, request.form)
        db.session.commit()
        flash("Семинар обновлён", "success")
        return redirect(url_for("seminars.seminars_detail", seminar_id=seminar.id))
    return render_template("seminars/form.html", seminar=seminar, references=references)


@bp.route("/<int:seminar_id>/delete", methods=["POST"])
def seminars_delete(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    db.session.delete(seminar)
    db.session.commit()
    flash("Семинар удалён", "success")
    return redirect(url_for("seminars.seminars_list"))


# --- Заявки на участие в семинаре ---

def _fill_application_from_form(application, form):
    application.region = form.get("region", "").strip() or None
    application.organization_name = form.get("organization_name", "").strip() or None
    application.sending_org_name = form.get("sending_org_name", "").strip() or None
    application.sending_org_leader_name = form.get("sending_org_leader_name", "").strip() or None
    application.sending_org_leader_position = form.get("sending_org_leader_position", "").strip() or None
    application.sending_org_leader_phone = form.get("sending_org_leader_phone", "").strip() or None
    application.sending_org_leader_email = form.get("sending_org_leader_email", "").strip() or None


def _sync_participants(application, form):
    for participant in list(application.participants):
        db.session.delete(participant)

    judge_ids = form.getlist("participant_judge_id[]")
    full_names = form.getlist("participant_full_name[]")
    genders = form.getlist("participant_gender[]")
    birth_dates = form.getlist("participant_birth_date[]")
    qualifications = form.getlist("participant_qualification[]")
    categories = form.getlist("participant_category[]")
    specializations = form.getlist("participant_specialization[]")

    for i, full_name in enumerate(full_names):
        full_name = full_name.strip()
        if not full_name:
            continue
        judge_id_raw = judge_ids[i].strip() if i < len(judge_ids) else ""
        db.session.add(SeminarApplicationParticipant(
            application_id=application.id,
            judge_id=int(judge_id_raw) if judge_id_raw.isdigit() else None,
            full_name=full_name,
            gender=(genders[i].strip() or None) if i < len(genders) else None,
            birth_date=_parse_date(birth_dates[i]) if i < len(birth_dates) else None,
            judge_qualification=(qualifications[i].strip() or None) if i < len(qualifications) else None,
            assigned_category=(categories[i].strip() or None) if i < len(categories) else None,
            specialization=(specializations[i].strip() or None) if i < len(specializations) else None,
        ))


@bp.route("/<int:seminar_id>/applications")
def applications_list(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    applications = SeminarApplication.query.filter_by(seminar_id=seminar_id).order_by(SeminarApplication.region).all()
    regions_count = len({a.region for a in applications if a.region})
    return render_template(
        "seminars/applications/list.html", seminar=seminar,
        applications=applications, regions_count=regions_count,
    )


@bp.route("/<int:seminar_id>/applications/toggle-status", methods=["POST"])
def applications_toggle_status(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    seminar.applications_done = not seminar.applications_done
    db.session.commit()
    return redirect(url_for("seminars.applications_list", seminar_id=seminar.id))


@bp.route("/<int:seminar_id>/applications/new", methods=["GET", "POST"])
def applications_new(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    if request.method == "POST":
        application = SeminarApplication(seminar_id=seminar.id)
        _fill_application_from_form(application, request.form)
        db.session.add(application)
        db.session.flush()
        _sync_participants(application, request.form)
        db.session.commit()
        flash("Заявка добавлена", "success")
        return redirect(url_for("seminars.applications_list", seminar_id=seminar.id))
    return render_template(
        "seminars/applications/form.html", seminar=seminar, application=None,
        references=references, judge_qualifications=JUDGE_QUALIFICATIONS,
    )


@bp.route("/<int:seminar_id>/applications/<int:application_id>/edit", methods=["GET", "POST"])
def applications_edit(seminar_id, application_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    application = SeminarApplication.query.get_or_404(application_id)
    if request.method == "POST":
        _fill_application_from_form(application, request.form)
        _sync_participants(application, request.form)
        db.session.commit()
        flash("Заявка обновлена", "success")
        return redirect(url_for("seminars.applications_list", seminar_id=seminar.id))
    return render_template(
        "seminars/applications/form.html", seminar=seminar, application=application,
        references=references, judge_qualifications=JUDGE_QUALIFICATIONS,
    )


@bp.route("/<int:seminar_id>/applications/<int:application_id>/delete", methods=["POST"])
def applications_delete(seminar_id, application_id):
    application = SeminarApplication.query.get_or_404(application_id)
    db.session.delete(application)
    db.session.commit()
    flash("Заявка удалена", "success")
    return redirect(url_for("seminars.applications_list", seminar_id=seminar_id))


@bp.route("/<int:seminar_id>/applications/<int:application_id>/print")
def applications_print(seminar_id, application_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    application = SeminarApplication.query.get_or_404(application_id)
    return render_template("seminars/applications/print.html", seminar=seminar, application=application)


# --- Протокол семинара ---

def _fill_protocol_from_form(seminar, form):
    seminar.protocol_number = form.get("protocol_number", "").strip() or None
    seminar.federation_full_name = form.get("federation_full_name", "").strip() or None
    seminar.deputy_full_name = form.get("deputy_full_name", "").strip() or None
    seminar.deputy_category = form.get("deputy_category", "").strip() or None
    seminar.deputy_region = form.get("deputy_region", "").strip() or None


def _sync_protocol_participants(form):
    participant_ids = form.getlist("protocol_participant_id[]")
    participant_hours = form.getlist("protocol_participant_hours[]")
    lecturer_hours = form.getlist("protocol_lecturer_hours[]")
    exam_results = form.getlist("protocol_exam_result[]")
    certificate_numbers = form.getlist("protocol_certificate_number[]")

    for i, pid_raw in enumerate(participant_ids):
        pid_raw = pid_raw.strip()
        if not pid_raw.isdigit():
            continue
        participant = SeminarApplicationParticipant.query.get(int(pid_raw))
        if not participant:
            continue
        participant.theory_participant_hours = (participant_hours[i].strip() or None) if i < len(participant_hours) else None
        participant.theory_lecturer_hours = (lecturer_hours[i].strip() or None) if i < len(lecturer_hours) else None
        participant.exam_result = (exam_results[i].strip() or None) if i < len(exam_results) else None
        participant.certificate_number = (certificate_numbers[i].strip() or None) if i < len(certificate_numbers) else None


def _default_theory_hours(seminar, participant):
    """Часы теоретических занятий участника — из карточки семинара (программа семинара, количество часов),
    если присваиваемая (подтверждаемая) категория участника совпадает с категорией семинара."""
    if not seminar.program_hours or not participant.assigned_category:
        return None
    if participant.assigned_category != seminar.category:
        return None
    digits = "".join(ch for ch in seminar.program_hours if ch.isdigit())
    return digits or None


def _protocol_participants(seminar_id, seminar):
    participants = (
        SeminarApplicationParticipant.query
        .join(SeminarApplication, SeminarApplicationParticipant.application_id == SeminarApplication.id)
        .filter(SeminarApplication.seminar_id == seminar_id)
        .order_by(SeminarApplicationParticipant.full_name)
        .all()
    )
    for p in participants:
        p.default_hours = _default_theory_hours(seminar, p)
    return participants


@bp.route("/<int:seminar_id>/protocol", methods=["GET", "POST"])
def protocol_edit(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    if request.method == "POST":
        _fill_protocol_from_form(seminar, request.form)
        _sync_protocol_participants(request.form)
        db.session.commit()
        flash("Данные протокола сохранены", "success")
        return redirect(url_for("seminars.protocol_edit", seminar_id=seminar.id))
    participants = _protocol_participants(seminar_id, seminar)
    return render_template(
        "seminars/protocol/edit.html", seminar=seminar, participants=participants,
        references=references,
    )


@bp.route("/<int:seminar_id>/protocol/print")
def protocol_print(seminar_id):
    seminar = Seminar.query.get_or_404(seminar_id)
    participants = _protocol_participants(seminar_id, seminar)
    return render_template("seminars/protocol/print.html", seminar=seminar, participants=participants)
