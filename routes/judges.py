# routes/judges.py — карточки спортивных судей, история категорий/подготовки/практики
import os
from datetime import datetime

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for

import references
from judge_docx_generator import generate_judge_card, judge_card_filename
from judge_docx_importer import parse_judge_card
from models import (
    Judge, JudgeCategoryRecord, JudgeCompetitionRecord, JudgeTrainingRecord, Settings, db,
)

bp = Blueprint("judges", __name__, url_prefix="/judges")

PHOTO_UPLOAD_SUBDIR = os.path.join("uploads", "judges")
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

_CATEGORY_TO_ABBR = {full: abbr for abbr, full in references.JUDGE_CATEGORY_ABBREVIATIONS.items()}

# Кнопки на странице «Список спортивных судей» — по квалификационным категориям
JUDGE_CATEGORY_TYPES = [
    ("/vsk", "ССВК", "judges.judges_vsk",
     "Спортивный судья всероссийской категории", "Спортивные судьи всероссийской категории"),
    ("/1k", "СС1К", "judges.judges_1k",
     "Спортивный судья первой категории", "Спортивные судьи первой категории"),
    ("/2k", "СС2К", "judges.judges_2k",
     "Спортивный судья второй категории", "Спортивные судьи второй категории"),
    ("/3k", "СС3К", "judges.judges_3k",
     "Спортивный судья третьей категории", "Спортивные судьи третьей категории"),
]


def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _fill_judge_from_form(judge, form):
    judge.last_name = form.get("last_name", "").strip()
    judge.first_name = form.get("first_name", "").strip()
    judge.middle_name = form.get("middle_name", "").strip() or None
    judge.birth_date = _parse_date(form.get("birth_date"))
    judge.region = form.get("region", "").strip() or None
    judge.municipality = form.get("municipality", "").strip() or None
    judge.rank = form.get("rank", "").strip() or None
    judge.education = form.get("education", "").strip() or None
    judge.workplace = form.get("workplace", "").strip() or None
    judge.contacts = form.get("contacts", "").strip() or None
    judge.specialization = form.get("specialization", "").strip() or None
    judge.discipline_group = form.get("discipline_group", "").strip() or None
    judge.judging_start_date = _parse_date(form.get("judging_start_date"))


def _photo_upload_dir():
    path = os.path.join(current_app.static_folder, PHOTO_UPLOAD_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _delete_photo_file(filename):
    path = os.path.join(_photo_upload_dir(), filename)
    if os.path.exists(path):
        os.remove(path)


def _save_photo(judge, file_storage):
    if not file_storage or not file_storage.filename:
        return False
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        flash("Недопустимый формат фотографии (допустимо: jpg, jpeg, png, gif, webp)", "error")
        return False
    old_filename = judge.photo_filename
    filename = f"judge_{judge.id}.{ext}"
    file_storage.save(os.path.join(_photo_upload_dir(), filename))
    judge.photo_filename = filename
    if old_filename and old_filename != filename:
        _delete_photo_file(old_filename)
    return True


@bp.route("/")
def judges_list():
    municipality = request.args.get("municipality", "")
    specialization = request.args.get("specialization", "")
    discipline_group = request.args.get("discipline_group", "")

    query = Judge.query.filter_by(is_active=True)
    if municipality:
        query = query.filter_by(municipality=municipality)
    if specialization:
        query = query.filter_by(specialization=specialization)
    if discipline_group:
        query = query.filter_by(discipline_group=discipline_group)
    judges = query.order_by(Judge.last_name).all()

    return render_template(
        "judges/list.html", judges=judges, heading="Список спортивных судей",
        list_buttons=JUDGE_CATEGORY_TYPES, show_add_button=True, highlight_active=False,
        show_filters=True,
        filters={
            "municipality": municipality, "specialization": specialization,
            "discipline_group": discipline_group,
        },
        municipality_options=_distinct_municipalities(),
        specialization_options=references.JUDGE_SPECIALIZATIONS,
        discipline_group_options=references.JUDGE_DISCIPLINE_GROUPS,
    )


def _distinct_municipalities():
    rows = (
        db.session.query(Judge.municipality)
        .filter(Judge.municipality.isnot(None), Judge.municipality != "")
        .distinct()
        .order_by(Judge.municipality)
        .all()
    )
    return [row[0] for row in rows]


def _make_category_view(category, heading):
    def view():
        municipality = request.args.get("municipality", "")
        specialization = request.args.get("specialization", "")
        discipline_group = request.args.get("discipline_group", "")

        judges = [
            j for j in Judge.query.order_by(Judge.last_name).all()
            if j.current_category == category
        ]
        if municipality:
            judges = [j for j in judges if j.municipality == municipality]
        if specialization:
            judges = [j for j in judges if j.specialization == specialization]
        if discipline_group:
            judges = [j for j in judges if j.discipline_group == discipline_group]

        return render_template(
            "judges/list.html", judges=judges, heading=heading,
            show_add_button=False, highlight_active=True,
            show_filters=True,
            filters={
                "municipality": municipality, "specialization": specialization,
                "discipline_group": discipline_group,
            },
            municipality_options=_distinct_municipalities(),
            specialization_options=references.JUDGE_SPECIALIZATIONS,
            discipline_group_options=references.JUDGE_DISCIPLINE_GROUPS,
        )
    return view


for _path, _label, _endpoint, _category, _heading in JUDGE_CATEGORY_TYPES:
    bp.add_url_rule(
        _path,
        endpoint=_endpoint.split(".")[1],
        view_func=_make_category_view(_category, _heading),
    )


@bp.route("/new", methods=["GET", "POST"])
def judges_new():
    if request.method == "POST":
        judge = Judge()
        _fill_judge_from_form(judge, request.form)
        db.session.add(judge)
        db.session.commit()
        _save_photo(judge, request.files.get("photo"))
        db.session.commit()
        flash("Судья добавлен", "success")
        return redirect(url_for("judges.judges_detail", judge_id=judge.id))
    return render_template("judges/form.html", judge=None, references=references)


@bp.route("/import", methods=["GET", "POST"])
def judges_import():
    if request.method == "POST":
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            flash("Выберите хотя бы один файл .docx", "error")
            return redirect(url_for("judges.judges_import"))

        imported = []
        errors = []
        for file_storage in files:
            try:
                judge = parse_judge_card(file_storage.stream)
                if not judge.last_name or not judge.first_name:
                    raise ValueError("не удалось распознать фамилию и имя судьи")
                db.session.add(judge)
                db.session.flush()
                imported.append(judge)
            except Exception:
                errors.append(file_storage.filename)

        db.session.commit()

        if imported:
            flash(f"Импортировано карточек: {len(imported)} ({', '.join(j.full_name for j in imported)})", "success")
        if errors:
            flash(f"Не удалось импортировать: {', '.join(errors)}", "error")

        if len(imported) == 1 and not errors:
            return redirect(url_for("judges.judges_detail", judge_id=imported[0].id))
        return redirect(url_for("judges.judges_list"))

    return render_template("judges/import.html")


@bp.route("/search")
def judges_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    like = f"%{q}%"
    judges = (
        Judge.query.filter(
            db.or_(Judge.last_name.ilike(like), Judge.first_name.ilike(like), Judge.middle_name.ilike(like))
        )
        .order_by(Judge.last_name)
        .limit(20)
        .all()
    )
    return jsonify([
        {
            "id": j.id,
            "full_name": j.full_name,
            "birth_date": j.birth_date.isoformat() if j.birth_date else "",
            "region": j.region or "",
            "qualification": _CATEGORY_TO_ABBR.get(j.current_category, ""),
        }
        for j in judges
    ])


@bp.route("/<int:judge_id>")
def judges_detail(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    return render_template("judges/detail.html", judge=judge, references=references)


@bp.route("/<int:judge_id>/photo", methods=["POST"])
def judges_photo_upload(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    if _save_photo(judge, request.files.get("photo")):
        db.session.commit()
        flash("Фотография обновлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/<int:judge_id>/photo/delete", methods=["POST"])
def judges_photo_delete(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    if judge.photo_filename:
        _delete_photo_file(judge.photo_filename)
        judge.photo_filename = None
        db.session.commit()
        flash("Фотография удалена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/<int:judge_id>/edit", methods=["GET", "POST"])
def judges_edit(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    if request.method == "POST":
        _fill_judge_from_form(judge, request.form)
        _save_photo(judge, request.files.get("photo"))
        db.session.commit()
        flash("Изменения сохранены", "success")
        return redirect(url_for("judges.judges_detail", judge_id=judge.id))
    return render_template("judges/form.html", judge=judge, references=references)


@bp.route("/<int:judge_id>/deactivate", methods=["POST"])
def judges_deactivate(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    judge.is_active = False
    db.session.commit()
    flash("Судья исключён из списка", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/<int:judge_id>/activate", methods=["POST"])
def judges_activate(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    judge.is_active = True
    db.session.commit()
    flash("Судья возвращён в список", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/<int:judge_id>/delete", methods=["POST"])
def judges_delete(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    if judge.photo_filename:
        _delete_photo_file(judge.photo_filename)
    db.session.delete(judge)
    db.session.commit()
    flash("Судья удалён", "success")
    return redirect(url_for("judges.judges_list"))


@bp.route("/<int:judge_id>/export")
def judges_export(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    settings = Settings.query.first()
    buffer = generate_judge_card(judge, settings)
    return send_file(
        buffer, as_attachment=True, download_name=judge_card_filename(judge),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# --- История квалификационных категорий ---

def _fill_category_record(record, form):
    record.category = form.get("category", "").strip() or None
    record.action = form.get("action", "").strip() or None
    record.date = _parse_date(form.get("date"))
    record.document_number = form.get("document_number", "").strip() or None
    record.issuing_organization = form.get("issuing_organization", "").strip() or None
    record.signed_by = form.get("signed_by", "").strip() or None
    record.record_keeper = form.get("record_keeper", "").strip() or None


@bp.route("/<int:judge_id>/category-records", methods=["POST"])
def category_record_add(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    record = JudgeCategoryRecord(judge_id=judge.id)
    _fill_category_record(record, request.form)
    db.session.add(record)
    db.session.commit()
    flash("Запись о категории добавлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/category-records/<int:record_id>/edit", methods=["POST"])
def category_record_edit(record_id):
    record = JudgeCategoryRecord.query.get_or_404(record_id)
    _fill_category_record(record, request.form)
    db.session.commit()
    flash("Запись о категории обновлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=record.judge_id))


@bp.route("/category-records/<int:record_id>/delete", methods=["POST"])
def category_record_delete(record_id):
    record = JudgeCategoryRecord.query.get_or_404(record_id)
    judge_id = record.judge_id
    db.session.delete(record)
    db.session.commit()
    flash("Запись о категории удалена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge_id))


# --- Теоретическая подготовка, сдача квалификационного зачёта ---

def _fill_training_record(record, form):
    record.seminar_name = form.get("seminar_name", "").strip() or None
    record.seminar_date = form.get("seminar_date", "").strip() or None
    record.organizer = form.get("organizer", "").strip() or None
    record.location = form.get("location", "").strip() or None
    record.participant_category = form.get("participant_category", "").strip() or None
    record.participant_score = form.get("participant_score", "").strip() or None
    record.participant_date = form.get("participant_date", "").strip() or None
    record.lecturer_category = form.get("lecturer_category", "").strip() or None
    record.lecturer_score = form.get("lecturer_score", "").strip() or None
    record.lecturer_date = form.get("lecturer_date", "").strip() or None
    record.exam_protocol_number = form.get("exam_protocol_number", "").strip() or None
    record.exam_score = form.get("exam_score", "").strip() or None
    record.record_date = form.get("record_date", "").strip() or None
    record.record_keeper = form.get("record_keeper", "").strip() or None


@bp.route("/<int:judge_id>/training-records", methods=["POST"])
def training_record_add(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    record = JudgeTrainingRecord(judge_id=judge.id)
    _fill_training_record(record, request.form)
    db.session.add(record)
    db.session.commit()
    flash("Запись о подготовке добавлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/training-records/<int:record_id>/edit", methods=["POST"])
def training_record_edit(record_id):
    record = JudgeTrainingRecord.query.get_or_404(record_id)
    _fill_training_record(record, request.form)
    db.session.commit()
    flash("Запись о подготовке обновлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=record.judge_id))


@bp.route("/training-records/<int:record_id>/delete", methods=["POST"])
def training_record_delete(record_id):
    record = JudgeTrainingRecord.query.get_or_404(record_id)
    judge_id = record.judge_id
    db.session.delete(record)
    db.session.commit()
    flash("Запись о подготовке удалена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge_id))


# --- Практика судейства официальных спортивных соревнований ---

def _fill_competition_record(record, form):
    record.event_date = form.get("event_date", "").strip() or None
    record.location = form.get("location", "").strip() or None
    record.judge_position = form.get("judge_position", "").strip() or None
    record.competition_name = form.get("competition_name", "").strip() or None
    record.competition_status = form.get("competition_status", "").strip() or None
    record.score = form.get("score", "").strip() or None
    record.record_date = form.get("record_date", "").strip() or None
    record.record_keeper = form.get("record_keeper", "").strip() or None


@bp.route("/<int:judge_id>/competition-records", methods=["POST"])
def competition_record_add(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    record = JudgeCompetitionRecord(judge_id=judge.id)
    _fill_competition_record(record, request.form)
    db.session.add(record)
    db.session.commit()
    flash("Запись о практике судейства добавлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge.id))


@bp.route("/competition-records/<int:record_id>/edit", methods=["POST"])
def competition_record_edit(record_id):
    record = JudgeCompetitionRecord.query.get_or_404(record_id)
    _fill_competition_record(record, request.form)
    db.session.commit()
    flash("Запись о практике судейства обновлена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=record.judge_id))


@bp.route("/competition-records/<int:record_id>/delete", methods=["POST"])
def competition_record_delete(record_id):
    record = JudgeCompetitionRecord.query.get_or_404(record_id)
    judge_id = record.judge_id
    db.session.delete(record)
    db.session.commit()
    flash("Запись о практике судейства удалена", "success")
    return redirect(url_for("judges.judges_detail", judge_id=judge_id))
