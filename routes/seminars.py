# routes/seminars.py — семинары по подготовке спортивных судей по рафтингу
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

import references
from models import Seminar, db

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
