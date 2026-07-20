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
    specialization = db.Column(db.String(300))  # Специализация
    discipline_group = db.Column(db.String(300))  # Группа спортивных дисциплин

    judging_start_date = db.Column(db.Date)     # Дата начала судейской деятельности спортивного судьи

    photo_filename = db.Column(db.String(300))  # имя файла фотографии в static/uploads/judges/

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


class Seminar(db.Model):
    """Семинар по подготовке спортивных судей по рафтингу."""
    __tablename__ = "seminar"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(500))            # Наименование семинара

    start_date = db.Column(db.Date)              # Дата начала семинара
    period = db.Column(db.String(150))           # Сроки проведения семинара
    location = db.Column(db.String(300))         # Место проведения семинара

    # Идентификаторы семинара
    category = db.Column(db.String(100))         # Наименование присваиваемой (подтверждаемой) категории
    organizer = db.Column(db.String(300))         # Организация, проводящая семинар
    program_hours = db.Column(db.String(20))      # Программа семинара (количество часов)
    qualification_exam = db.Column(db.String(10))  # Квалификационный зачёт: Да/Нет

    # Руководитель семинара
    leader_full_name = db.Column(db.String(200))
    leader_category = db.Column(db.String(100))   # Квалификация спортивного судьи
    leader_region = db.Column(db.String(150))      # Субъект Российской Федерации
    leader_phone = db.Column(db.String(100))

    applications_done = db.Column(db.Boolean, default=False, nullable=False)  # статус блока «Заявки на участие»
    lecturers_done = db.Column(db.Boolean, default=False, nullable=False)     # статус блока «Преподавательский состав»
    protocol_done = db.Column(db.Boolean, default=False, nullable=False)      # статус блока «Протокол»
    gradesheet_done = db.Column(db.Boolean, default=False, nullable=False)    # статус протокола сдачи квалификационного зачёта

    # Данные протокола семинара
    protocol_number = db.Column(db.String(50))       # № протокола, напр. «1/04-2025»
    protocol_region = db.Column(db.String(150))      # регион в шапке протокола
    federation_full_name = db.Column(db.String(500))  # Полное наименование спортивной федерации
    deputy_full_name = db.Column(db.String(200))     # Завуч семинара
    deputy_category = db.Column(db.String(100))
    deputy_region = db.Column(db.String(150))

    # Данные положения о семинаре
    polozhenie_done = db.Column(db.Boolean, default=False, nullable=False)  # статус блока «Положение»

    # 1. Спортивная федерация по рафтингу
    polozhenie_federation_full_name = db.Column(db.String(500))
    polozhenie_federation_short_name = db.Column(db.String(100))
    polozhenie_federation_region = db.Column(db.String(150))       # Субъект Российской Федерации
    polozhenie_federation_leader_position = db.Column(db.String(200))  # Должность руководителя
    polozhenie_federation_leader_name = db.Column(db.String(200))      # ФИО руководителя
    polozhenie_federation_phone = db.Column(db.String(100))
    polozhenie_federation_email = db.Column(db.String(150))

    # 2. Сроки и место проведения семинара
    polozhenie_period = db.Column(db.String(200))       # Сроки проведения
    polozhenie_location = db.Column(db.String(300))     # Место проведения

    # 3. Программа
    polozhenie_program_hours = db.Column(db.String(20))  # Количество часов

    # 4. Размер заявочного взноса за участие
    polozhenie_fee_amount = db.Column(db.String(200))
    polozhenie_fee_requisites = db.Column(db.Text)
    polozhenie_fee_purpose = db.Column(db.String(300))

    # 5. Варианты проживания и питания участников
    polozhenie_accommodation = db.Column(db.Text)

    # 6. Проезд до места проведения
    polozhenie_travel = db.Column(db.Text)

    # 7. Заявки на участие
    polozhenie_applications_deadline = db.Column(db.Date)   # До даты
    polozhenie_applications_email = db.Column(db.String(150))  # По электронной почте
    polozhenie_applications_contacts = db.Column(db.Text)   # Контакты организаторов

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SeminarLecturer(db.Model):
    """Преподаватель (лектор) семинара по подготовке спортивных судей."""
    __tablename__ = "seminar_lecturer"

    id = db.Column(db.Integer, primary_key=True)
    seminar_id = db.Column(db.Integer, db.ForeignKey("seminar.id"), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey("judge.id"), nullable=True)

    full_name = db.Column(db.String(200))
    birth_date = db.Column(db.Date)
    region = db.Column(db.String(150))             # Субъект Российской Федерации
    gender = db.Column(db.String(10))

    qualification = db.Column(db.String(100))      # Квалификация спортивного судьи
    category_assigned_date = db.Column(db.Date)    # Дата присвоения
    category_confirmed_date = db.Column(db.Date)   # Дата подтверждения
    category_reattestation_date = db.Column(db.Date)  # Дата переаттестации
    is_active_category = db.Column(db.Boolean, default=True)  # Статус категории: действующая

    position = db.Column(db.String(100))           # Должность на семинаре
    lecture_hours = db.Column(db.String(20))       # Количество часов в качестве лектора
    participant_hours = db.Column(db.String(20))   # Количество часов теоретической подготовки в качестве участника
    exam_result = db.Column(db.String(20))         # Оценка сдачи квалификационного зачёта

    seminar = db.relationship("Seminar", backref=db.backref(
        "lecturers", cascade="all, delete-orphan", order_by="SeminarLecturer.id",
    ))
    judge = db.relationship("Judge")


class SeminarApplication(db.Model):
    """Заявка на участие в семинаре (от направляющей организации субъекта РФ)."""
    __tablename__ = "seminar_application"

    id = db.Column(db.Integer, primary_key=True)
    seminar_id = db.Column(db.Integer, db.ForeignKey("seminar.id"), nullable=False)

    region = db.Column(db.String(150))               # Субъект Российской Федерации
    organization_name = db.Column(db.String(300))     # Наименование организации

    # Данные организации, направляющей команду на соревнования
    sending_org_name = db.Column(db.String(300))
    sending_org_leader_name = db.Column(db.String(200))
    sending_org_leader_position = db.Column(db.String(150))
    sending_org_leader_phone = db.Column(db.String(100))
    sending_org_leader_email = db.Column(db.String(150))

    # Данные руководителя организации
    org_leader_full_name = db.Column(db.String(200))
    org_leader_phone = db.Column(db.String(100))
    org_leader_email = db.Column(db.String(150))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seminar = db.relationship("Seminar", backref=db.backref("applications", cascade="all, delete-orphan"))


class SeminarApplicationParticipant(db.Model):
    """Участник заявки на семинар — запись из базы судей либо произвольно введённая."""
    __tablename__ = "seminar_application_participant"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("seminar_application.id"), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey("judge.id"), nullable=True)

    full_name = db.Column(db.String(200))
    gender = db.Column(db.String(10))
    birth_date = db.Column(db.Date)
    judge_qualification = db.Column(db.String(100))   # Квалификация спортивного судьи
    assigned_category = db.Column(db.String(100))     # Присваиваемая (подтверждаемая) категория
    specialization = db.Column(db.String(300))        # Специализация

    # Данные протокола семинара
    theory_participant_hours = db.Column(db.String(20))  # Кол-во теор. занятий в качестве участника (не используется, оставлено для совместимости)
    theory_lecturer_hours = db.Column(db.String(20))     # Кол-во теор. занятий в качестве лектора (не используется, оставлено для совместимости)
    exam_result = db.Column(db.String(20))               # Оценка сдачи квалификационного зачёта
    certificate_number = db.Column(db.String(50))        # № справки

    # Данные протокола сдачи квалификационного зачёта
    test_questions_count = db.Column(db.String(20))      # Количество тестовых вопросов
    correct_answers_count = db.Column(db.String(20))     # Количество правильных ответов

    application = db.relationship("SeminarApplication", backref=db.backref(
        "participants", order_by="SeminarApplicationParticipant.id", cascade="all, delete-orphan",
    ))
    judge = db.relationship("Judge")
