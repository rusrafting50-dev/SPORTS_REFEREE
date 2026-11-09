# judge_docx_importer.py — импорт данных из готовой docx-карточки судьи
# («Карточка учёта судейской деятельности спортивного судьи») в новую
# запись Judge с историей категорий/подготовки/практики
import re
from datetime import date

import docx
from docx.oxml.ns import qn

from models import Judge, JudgeCategoryRecord, JudgeCompetitionRecord, JudgeTrainingRecord

_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _cell(table, row, col):
    """Текст ячейки по индексу физической <w:tc> в строке (а не индексу
    сетки таблицы) — так же, как ячейки заполняются в judge_docx_generator.py,
    поскольку строки шапки/истории категорий содержат объединённые по
    горизонтали ячейки (gridSpan), из-за чего индекс сетки не совпадает
    с порядковым номером ячейки."""
    try:
        tr = table.rows[row]._tr
    except IndexError:
        return ""
    tcs = tr.findall(qn("w:tc"))
    if col >= len(tcs):
        return ""
    texts = tcs[col].findall(".//" + qn("w:t"))
    return "".join(t.text or "" for t in texts).strip()


def _row_blank(table, row, cols):
    return all(not _cell(table, row, c) for c in cols)


def _parse_date_parts(day, month, year):
    if not (day.isdigit() and month.isdigit() and year.isdigit()):
        return None
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _parse_ddmmyyyy(text):
    match = _DATE_RE.search(text or "")
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_judge_card(file_obj):
    """Разбирает docx-карточку учёта судейской деятельности и возвращает
    новый объект Judge со связанными записями истории (без сохранения в БД)."""
    document = docx.Document(file_obj)
    tables = document.tables
    if len(tables) < 1:
        raise ValueError(f"В документе не найдено таблиц (найдено: {len(tables)})")
    table0 = tables[0]

    # Два варианта раскладки таблиц:
    # • 3 таблицы: table0=личные данные+категории, table1=подготовка, table2=соревнования
    # • 4 таблицы: table0=личные данные, table1=категории(~7 кол.), table2=подготовка, table3=соревнования
    # Определяем по числу столбцов второй таблицы: ≥12 → подготовка, иначе → категории
    if len(tables) >= 2 and len(tables[1].columns) >= 12:
        # 3-таблечный формат: категории внутри table0 (строки 14+)
        tbl_cat   = None          # читаем из table0
        tbl_train = tables[1] if len(tables) > 1 else None
        tbl_comp  = tables[2] if len(tables) > 2 else None
    else:
        # 4-таблечный формат: каждый раздел — своя таблица
        tbl_cat   = tables[1] if len(tables) > 1 else None
        tbl_train = tables[2] if len(tables) > 2 else None
        tbl_comp  = tables[3] if len(tables) > 3 else None

    judge = Judge(
        last_name=_cell(table0, 2, 1),
        first_name=_cell(table0, 2, 3),
        middle_name=_cell(table0, 2, 5) or None,
        region=_cell(table0, 4, 1) or None,
        municipality=_cell(table0, 4, 3) or None,
        rank=_cell(table0, 4, 5) or None,
        education=_cell(table0, 7, 1) or None,
        workplace=_cell(table0, 8, 1) or None,
        contacts=_cell(table0, 9, 1) or None,
        birth_date=_parse_date_parts(_cell(table0, 4, 6), _cell(table0, 4, 7), _cell(table0, 4, 8)),
        judging_start_date=_parse_date_parts(_cell(table0, 7, 2), _cell(table0, 7, 3), _cell(table0, 7, 4)),
    )

    # --- История квалификационных категорий ---
    # 3-табл.: раздел внутри table0, строки 14+
    # 4-табл.: отдельная таблица — строки 0–2 шапка, данные с 3-й
    if tbl_cat is None:
        cat_table, cat_start = table0, 14
    else:
        cat_table, cat_start = tbl_cat, 3
    for row in range(cat_start, len(cat_table.rows)):
        if _row_blank(cat_table, row, range(7)):
            continue
        judge.category_records.append(JudgeCategoryRecord(
            category=_cell(cat_table, row, 0) or None,
            action=_cell(cat_table, row, 1) or None,
            date=_parse_ddmmyyyy(_cell(cat_table, row, 2)),
            document_number=_cell(cat_table, row, 3) or None,
            issuing_organization=_cell(cat_table, row, 4) or None,
            signed_by=_cell(cat_table, row, 5) or None,
            record_keeper=_cell(cat_table, row, 6) or None,
        ))

    # --- Теоретическая подготовка (группы по 3 строки) ---
    # 3-табл.: данные с row 2 (шапка занимает строки 0–1)
    # 4-табл.: отдельная таблица — шапка строки 0–2, данные с row 3
    # В стандартном образце 13 столбцов (со столбцом "Дата" участника), в карточках,
    # выгруженных этим приложением, — 12 (столбец убран из отображения).
    if tbl_train is not None:
        train_start = 3 if tbl_cat is not None else 2
        has_participant_date = len(tbl_train.columns) >= 13
        for row in range(train_start, len(tbl_train.rows), 3):
            if row + 2 >= len(tbl_train.rows):
                break
            if _row_blank(tbl_train, row, range(6)):
                continue
            if has_participant_date:
                judge.training_records.append(JudgeTrainingRecord(
                    seminar_name=_cell(tbl_train, row, 0) or None,
                    seminar_date=_cell(tbl_train, row, 1) or None,
                    organizer=_cell(tbl_train, row, 2) or None,
                    location=_cell(tbl_train, row, 3) or None,
                    participant_category=_cell(tbl_train, row, 4) or None,
                    participant_score=_cell(tbl_train, row, 5) or None,
                    participant_date=_cell(tbl_train, row, 6) or None,
                    lecturer_category=_cell(tbl_train, row, 7) or None,
                    lecturer_score=_cell(tbl_train, row, 8) or None,
                    lecturer_date=_cell(tbl_train, row, 9) or None,
                    exam_protocol_number=_cell(tbl_train, row, 10) or None,
                    exam_score=_cell(tbl_train, row, 11) or None,
                    record_date=_cell(tbl_train, row, 12) or None,
                    record_keeper=_cell(tbl_train, row + 2, 12) or None,
                ))
            else:
                judge.training_records.append(JudgeTrainingRecord(
                    seminar_name=_cell(tbl_train, row, 0) or None,
                    seminar_date=_cell(tbl_train, row, 1) or None,
                    organizer=_cell(tbl_train, row, 2) or None,
                    location=_cell(tbl_train, row, 3) or None,
                    participant_category=_cell(tbl_train, row, 4) or None,
                    participant_score=_cell(tbl_train, row, 5) or None,
                    lecturer_category=_cell(tbl_train, row, 6) or None,
                    lecturer_score=_cell(tbl_train, row, 7) or None,
                    lecturer_date=_cell(tbl_train, row, 8) or None,
                    exam_protocol_number=_cell(tbl_train, row, 9) or None,
                    exam_score=_cell(tbl_train, row, 10) or None,
                    record_date=_cell(tbl_train, row, 11) or None,
                    record_keeper=_cell(tbl_train, row + 2, 11) or None,
                ))

    # --- Практика судейства официальных спортивных соревнований ---
    # Строки-заголовки и строки-продолжения пропускаются по отсутствию даты в col 0.
    # Количество строк на одну запись может быть разным (2–4), поэтому шаг динамический:
    # после обработки записи переходим к следующей строке с датой.
    if tbl_comp is not None:
        n_comp = len(tbl_comp.rows)
        crow = 0
        while crow < n_comp:
            # пропускаем строки без даты в col 0 (заголовки и строки-продолжения)
            if _parse_ddmmyyyy(_cell(tbl_comp, crow, 0) or "") is None:
                crow += 1
                continue
            # находим начало следующей записи (следующая строка с датой в col 0)
            next_crow = crow + 1
            while next_crow < n_comp and _parse_ddmmyyyy(_cell(tbl_comp, next_crow, 0) or "") is None:
                next_crow += 1
            # наименование и статус — первая непустая ячейка col 3 после текущей строки
            _name_status = ""
            for r in range(crow + 1, next_crow):
                v = _cell(tbl_comp, r, 3) or ""
                if v:
                    _name_status = v
                    break
            # секретарь — последняя непустая ячейка col 5 среди строк-продолжений
            _record_keeper = None
            for r in range(crow + 1, next_crow):
                v = _cell(tbl_comp, r, 5) or ""
                if v:
                    _record_keeper = v
            if "/" in _name_status:
                _name_part, _, _status_part = _name_status.partition("/")
                _comp_name   = _name_part.strip() or None
                _comp_status = _status_part.strip() or None
            else:
                _comp_name   = _name_status or None
                _comp_status = None
            judge.competition_records.append(JudgeCompetitionRecord(
                event_date=_cell(tbl_comp, crow, 0) or None,
                location=_cell(tbl_comp, crow, 1) or None,
                judge_position=_cell(tbl_comp, crow, 2) or None,
                competition_name=_comp_name,
                competition_status=_comp_status,
                score=_cell(tbl_comp, crow, 4) or None,
                record_date=_cell(tbl_comp, crow, 5) or None,
                record_keeper=_record_keeper,
            ))
            crow = next_crow

    return judge
