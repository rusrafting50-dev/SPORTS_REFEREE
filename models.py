# models.py — модели SQLAlchemy
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Athlete(db.Model):
    __tablename__ = "athlete"

    id = db.Column(db.Integer, primary_key=True)

    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))

    birth_date = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20), nullable=False)

    discipline = db.Column(db.String(300))
    category = db.Column(db.String(50))
    age_category = db.Column(db.String(50))
    rank = db.Column(db.String(50))

    organization = db.Column(db.String(300))
    territory = db.Column(db.String(100))
    trainer = db.Column(db.String(200))

    result_regional = db.Column(db.String(100))
    result_national = db.Column(db.String(100))
    result_international = db.Column(db.String(100))

    national_team = db.Column(db.String(200))

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    change_logs = db.relationship(
        "ChangeLog", backref="athlete", lazy=True, order_by="ChangeLog.change_date.desc()"
    )

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(p for p in parts if p)


class ChangeLog(db.Model):
    __tablename__ = "change_log"

    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey("athlete.id"), nullable=False)

    change_type = db.Column(db.String(20), nullable=False)  # 'включён' / 'исключён'
    change_date = db.Column(db.Date, nullable=False)
    document_number = db.Column(db.String(50))
    reason = db.Column(db.String(300))


class ReportSettings(db.Model):
    __tablename__ = "report_settings"

    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(300))
    chairman_position = db.Column(db.String(200))
    chairman_name = db.Column(db.String(200))
    head_coach_name = db.Column(db.String(200))
    sport_name = db.Column(db.String(200))
    year = db.Column(db.Integer)
