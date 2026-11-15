# seminar_cards.py — кнопка «Отправить в карточки» на странице «Протокол»:
# по каждой строке протокола семинара (участник и/или лектор) — запись в
# таблицу «Теоретическая подготовка» карточки судьи (JudgeTrainingRecord).
import re
from datetime import date

import references
from models import Judge, JudgeTrainingRecord, db

_MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}
_RE_NUMERIC = re.compile(r"\d{1,2}(?:\s*-\s*\d{1,2})?\.\d{1,2}\.\d{4}")
_RE_DAY_MONTH = re.compile(r"(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\s+(" + "|".join(_MONTHS) + r")[а-я]*", re.IGNORECASE)
_RE_YEAR = re.compile(r"\d{4}")


def _ru_plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def _hours_score(hours):
    """«16» -> «16 часов, зачёт»; без часов — просто «зачёт»."""
    digits = "".join(ch for ch in str(hours or "") if ch.isdigit())
    if not digits:
        return "зачёт"
    n = int(digits)
    return f"{n} {_ru_plural(n, 'час', 'часа', 'часов')}, зачёт"


def seminar_dates(seminar):
    """(текст «Дата» как в карточке, первый день, последний день).
    «07-08 декабря 2024 года» -> «07-08.12.2024»; «31 мая - 01 июня 2025» ->
    «31.05.2025-01.06.2025»; дни — строки «дд.мм.гггг»."""
    period = seminar.period or ""
    start = seminar.start_date
    numeric = _RE_NUMERIC.search(period)
    if numeric:
        text = numeric.group().replace(" ", "")
        d, m, y = text.split(".")
        first_day, last_day = d.split("-")[0], d.split("-")[-1]
        return text, f"{int(first_day):02d}.{m}.{y}", f"{int(last_day):02d}.{m}.{y}"

    parts = _RE_DAY_MONTH.findall(period)
    year_match = _RE_YEAR.search(period)
    year = year_match.group() if year_match else (str(start.year) if start else "")
    if parts and year:
        days = []
        for d1, d2, mon in parts:
            month = _MONTHS[mon.lower()[:3]]
            days.append((int(d1), month))
            if d2:
                days.append((int(d2), month))
        (fd, fm), (ld, lm) = days[0], days[-1]
        first, last = f"{fd:02d}.{fm:02d}.{year}", f"{ld:02d}.{lm:02d}.{year}"
        if first == last:
            text = first
        elif fm == lm:
            text = f"{fd:02d}-{ld:02d}.{fm:02d}.{year}"
        else:
            text = f"{first}-{last}"
        return text, first, last

    if start:
        day = start.strftime("%d.%m.%Y")
        return day, day, day
    return period.strip(), "", ""


def _full_category(abbr):
    return references.JUDGE_CATEGORY_ABBREVIATIONS.get(abbr, abbr or None)


def _norm_name(name):
    return " ".join((name or "").replace("ё", "е").replace("Ё", "Е").lower().split())


def _find_judge(row, judges_by_name):
    if row.judge_id:
        judge = db.session.get(Judge, row.judge_id)
        if judge:
            return judge
    return judges_by_name.get(_norm_name(row.full_name))


def _last_record_keeper(judge):
    for record in reversed(judge.training_records):
        if record.record_keeper:
            return record.record_keeper
    return None


def send_protocol_to_cards(seminar, rows):
    """Записывает строки протокола в карточки судей. Повторная отправка
    обновляет ранее созданную из этого семинара запись. Возвращает
    (сколько добавлено, сколько обновлено, ФИО не найденных в базе судей)."""
    judges_by_name = {}
    for judge in Judge.query.all():
        judges_by_name.setdefault(_norm_name(judge.full_name), judge)

    date_text, first_day, last_day = seminar_dates(seminar)
    today = date.today().strftime("%d.%m.%Y")
    added, updated, not_found = 0, 0, []

    for row in rows:
        judge = _find_judge(row, judges_by_name)
        if judge is None:
            not_found.append(row.full_name)
            continue

        record = JudgeTrainingRecord.query.filter_by(judge_id=judge.id, source_seminar_id=seminar.id).first()
        if record is None:
            record = JudgeTrainingRecord(judge_id=judge.id, source_seminar_id=seminar.id,
                                         record_keeper=_last_record_keeper(judge))
            db.session.add(record)
            added += 1
        else:
            updated += 1

        record.seminar_name = seminar.name
        record.seminar_date = date_text
        record.organizer = seminar.organizer
        record.location = seminar.location

        record.participant_category = _full_category(row.assigned_category)
        record.participant_score = _hours_score(row.participant_hours) if row.assigned_category else "-"

        if row.is_lecturer:
            record.lecturer_category = _full_category(row.current_qualification)
            record.lecturer_score = _hours_score(row.lecturer_hours)
            # participant_date хранит дату занятий в качестве лектора (см. judge_docx_importer)
            record.participant_date = first_day
        else:
            record.lecturer_category = "-"
            record.lecturer_score = "-"
            record.participant_date = None

        exam = (row.exam_result or "").strip()
        if exam and exam != "-":
            record.lecturer_date = last_day  # lecturer_date хранит дату сдачи зачёта
            record.exam_protocol_number = seminar.protocol_number
            record.exam_score = exam
        else:
            record.lecturer_date = record.exam_protocol_number = record.exam_score = "-"

        record.record_date = today

    db.session.commit()
    return added, updated, not_found
