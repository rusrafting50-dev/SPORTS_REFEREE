# models.py — модели SQLAlchemy
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Settings(db.Model):
    """Общая информация об организации для шапки карточки судьи."""
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)

    sport_name = db.Column(db.String(200))            # Наименование вида спорта
    sport_code = db.Column(db.String(50))              # Номер-код вида спорта

    organization_name = db.Column(db.String(300))      # Наименование организации, осуществляющей учёт судейской деятельности
    organization_address = db.Column(db.String(300))   # Адрес (место нахождения)
    organization_contacts = db.Column(db.String(300))  # Телефон, адрес электронной почты


class Judge(db.Model):
    __tablename__ = "judge"

    id = db.Column(db.Integer, primary_key=True)

    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))

    birth_date = db.Column(db.Date)
    region = db.Column(db.String(150))          # Субъект Российской Федерации
    municipality = db.Column(db.String(150))    # Муниципальное образование

    rank = db.Column(db.String(150))            # Спортивное звание в данном виде спорта (при наличии)
    education = db.Column(db.String(100))       # Образование
    workplace = db.Column(db.String(300))       # Место работы (учёбы), должность
    contacts = db.Column(db.String(300))        # Контактные телефоны, адрес электронной почты

    judging_start_date = db.Column(db.Date)     # Дата начала судейской деятельности спортивного судьи

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category_records = db.relationship(
        "JudgeCategoryRecord", backref="judge", lazy=True,
        order_by="JudgeCategoryRecord.date", cascade="all, delete-orphan",
    )
    training_records = db.relationship(
        "JudgeTrainingRecord", backref="judge", lazy=True,
        order_by="JudgeTrainingRecord.id", cascade="all, delete-orphan",
    )
    competition_records = db.relationship(
        "JudgeCompetitionRecord", backref="judge", lazy=True,
        order_by="JudgeCompetitionRecord.id", cascade="all, delete-orphan",
    )

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(p for p in parts if p)

    @property
    def current_category(self):
        """Последняя по дате запись из истории квалификационных категорий."""
        dated = [r for r in self.category_records if r.date]
        if not dated:
            return None
        return max(dated, key=lambda r: r.date).category


class JudgeCategoryRecord(db.Model):
    """История присвоения/подтверждения квалификационной категории спортивного судьи."""
    __tablename__ = "judge_category_record"

    id = db.Column(db.Integer, primary_key=True)
    judge_id = db.Column(db.Integer, db.ForeignKey("judge.id"), nullable=False)

    category = db.Column(db.String(100))            # Наименование квалификационной категории
    action = db.Column(db.String(50))                # присвоена / подтверждена / лишена / восстановлена
    date = db.Column(db.Date)
    document_number = db.Column(db.String(50))
    issuing_organization = db.Column(db.String(300))  # принявшая решение
    signed_by = db.Column(db.String(150))             # подписавшее должностное лицо
    record_keeper = db.Column(db.String(150))         # ответственный за оформление карточки


class JudgeTrainingRecord(db.Model):
    """Прохождение теоретической подготовки спортивного судьи, сдача квалификационного зачёта."""
    __tablename__ = "judge_training_record"

    id = db.Column(db.Integer, primary_key=True)
    judge_id = db.Column(db.Integer, db.ForeignKey("judge.id"), nullable=False)

    seminar_name = db.Column(db.String(500))
    seminar_date = db.Column(db.String(50))
    organizer = db.Column(db.String(200))
    location = db.Column(db.String(200))

    participant_category = db.Column(db.String(150))  # спортивная квалификация — участник
    participant_score = db.Column(db.String(150))
    participant_date = db.Column(db.String(50))

    lecturer_category = db.Column(db.String(150))      # спортивная квалификация — лектор
    lecturer_score = db.Column(db.String(150))
    lecturer_date = db.Column(db.String(50))

    exam_protocol_number = db.Column(db.String(50))     # № протокола сдачи зачёта
    exam_score = db.Column(db.String(50))

    record_date = db.Column(db.String(50))               # дата внесения записи
    record_keeper = db.Column(db.String(150))            # ответственный за оформление карточки


class JudgeCompetitionRecord(db.Model):
    """Практика судейства официальных спортивных соревнований."""
    __tablename__ = "judge_competition_record"

    id = db.Column(db.Integer, primary_key=True)
    judge_id = db.Column(db.Integer, db.ForeignKey("judge.id"), nullable=False)

    event_date = db.Column(db.String(50))
    location = db.Column(db.String(200))
    judge_position = db.Column(db.String(150))            # наименование должности спортивного судьи
    competition_name = db.Column(db.String(500))          # наименование и вид программы соревнования
    competition_status = db.Column(db.String(200))        # статус официального соревнования
    score = db.Column(db.String(50))

    record_date = db.Column(db.String(50))
    record_keeper = db.Column(db.String(150))
