# routes/api.py — приём заявок на семинар с сайта RAFTING_CFO
#
# Сайт RAFTING_CFO шлёт сюда заявки, поданные зарегистрированными
# пользователями (представителями регионов) — POST создаёт новую заявку
# (историю не перезаписываем, у каждой заявки своя дата/время), GET отдаёт
# список уже поданных заявок для отображения на странице мероприятия на
# сайте. Оба защищены заголовком X-API-Key (значение — в .env, API_KEY).
import os
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request

from models import Seminar, SeminarApplication, SeminarApplicationParticipant, db

bp = Blueprint("api", __name__, url_prefix="/api")


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected_key = os.environ.get("API_KEY")
        provided_key = request.headers.get("X-API-Key")

        if not expected_key:
            return jsonify({"error": "API-ключ не настроен на сервере."}), 500
        if not provided_key or provided_key != expected_key:
            return jsonify({"error": "Неверный или отсутствующий X-API-Key."}), 401

        return view(*args, **kwargs)
    return wrapped


def _parse_datetime(value):
    """ISO datetime строкой (submitted_at от RAFTING_CFO) -> datetime.
    Нет или не распозналось — None (тогда используется время получения)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _application_to_dict(application):
    return {
        "id": application.id,
        "region": application.region,
        "organization_name": application.organization_name,
        "sending_org_name": application.sending_org_name,
        "sending_org_leader_name": application.sending_org_leader_name,
        "sending_org_leader_position": application.sending_org_leader_position,
        "sending_org_leader_phone": application.sending_org_leader_phone,
        "sending_org_leader_email": application.sending_org_leader_email,
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "source": "сайт" if application.source == "site" else "SPORTS_REFEREE",
        "participants": [
            {
                "full_name": p.full_name,
                "gender": p.gender,
                "birth_date": p.birth_date.isoformat() if p.birth_date else None,
                "judge_qualification": p.judge_qualification,
                "assigned_category": p.assigned_category,
                "specialization": p.specialization,
            }
            for p in application.participants
        ],
    }


@bp.route("/seminars/<int:seminar_id>/applications", methods=["GET"])
@require_api_key
def applications_get(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if seminar is None:
        return jsonify({"error": "Семинар не найден."}), 404

    applications = (
        SeminarApplication.query.filter_by(seminar_id=seminar_id)
        .order_by(SeminarApplication.created_at.desc())
        .all()
    )
    return jsonify({"status": "ok", "items": [_application_to_dict(a) for a in applications]})


@bp.route("/seminars/<int:seminar_id>/applications", methods=["POST"])
@require_api_key
def applications_post(seminar_id):
    seminar = Seminar.query.get(seminar_id)
    if seminar is None:
        return jsonify({"error": "Семинар не найден."}), 404

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Тело запроса должно быть JSON-объектом."}), 400

    participants_raw = payload.get("participants")
    if not isinstance(participants_raw, list) or not participants_raw:
        return jsonify({"error": "Нужен непустой список участников (participants)."}), 400

    application = SeminarApplication(
        seminar_id=seminar.id,
        region=(payload.get("region") or "").strip() or None,
        organization_name=(payload.get("organization_name") or "").strip() or None,
        sending_org_name=(payload.get("sending_org_name") or "").strip() or None,
        sending_org_leader_name=(payload.get("sending_org_leader_name") or "").strip() or None,
        sending_org_leader_position=(payload.get("sending_org_leader_position") or "").strip() or None,
        sending_org_leader_phone=(payload.get("sending_org_leader_phone") or "").strip() or None,
        sending_org_leader_email=(payload.get("sending_org_leader_email") or "").strip() or None,
        source="site",
    )
    submitted_at = _parse_datetime(payload.get("submitted_at"))
    if submitted_at:
        application.created_at = submitted_at
    db.session.add(application)
    db.session.flush()

    for item in participants_raw:
        full_name = (item.get("full_name") or "").strip()
        if not full_name:
            continue
        db.session.add(SeminarApplicationParticipant(
            application_id=application.id,
            full_name=full_name,
            gender=(item.get("gender") or "").strip() or None,
            birth_date=_parse_date(item.get("birth_date")),
            judge_qualification=(item.get("judge_qualification") or "").strip() or None,
            assigned_category=(item.get("assigned_category") or "").strip() or None,
            specialization=(item.get("specialization") or "").strip() or None,
        ))

    db.session.commit()
    return jsonify({"status": "ok", "application_id": application.id})
