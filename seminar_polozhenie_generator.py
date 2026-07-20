# seminar_polozhenie_generator.py — генерация документа «Положение о семинаре»
# по структуре образца из data/Положение семинар СС3К_СС1К_MO_2025.doc
from io import BytesIO

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

POLOZHENIE_SECTIONS = [
    ("1. Цели и задачи", "polozhenie_goals"),
    ("2. Время и место проведения", "polozhenie_time_place"),
    ("3. Организаторы", "polozhenie_organizers"),
    ("4. Требования к участникам семинара", "polozhenie_requirements"),
    ("5. Программа семинара", "polozhenie_program"),
    ("6. Подведение итогов семинара", "polozhenie_results"),
    ("7. Условия приёма участников", "polozhenie_admission"),
    ("8. Финансирование", "polozhenie_financing"),
    ("9. Заявки на участие", "polozhenie_applications"),
]


def _fmt_date(value):
    return value.strftime("%d.%m.%Y") if value else ""


def _add_paragraph(document, text="", bold=False, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=6):
    p = document.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    return p


def generate_polozhenie(seminar, lecturers):
    document = docx.Document()

    style = document.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    _add_paragraph(document, "УТВЕРЖДАЮ", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=0)
    if seminar.polozhenie_approver_position:
        _add_paragraph(document, seminar.polozhenie_approver_position, align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=0)
    _add_paragraph(
        document,
        f"_________________ {seminar.polozhenie_approver_name or ''}".strip(),
        align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=0,
    )
    _add_paragraph(document, _fmt_date(seminar.polozhenie_approval_date), align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=24)

    _add_paragraph(document, "ПОЛОЖЕНИЕ", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
    _add_paragraph(
        document, seminar.polozhenie_title or seminar.name or "", bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18,
    )

    for title, field in POLOZHENIE_SECTIONS:
        _add_paragraph(document, title, bold=True, space_after=4)
        text = getattr(seminar, field) or ""
        for line in text.split("\n"):
            if line.strip():
                _add_paragraph(document, line.strip())
        if not text.strip():
            _add_paragraph(document, "")

    document.add_page_break()
    _add_paragraph(
        document, "Приложение 1", align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=0,
    )
    _add_paragraph(
        document, f"к положению {seminar.polozhenie_title or seminar.name or ''}",
        align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=18,
    )
    _add_paragraph(document, "ЛЕКТОРСКИЙ СОСТАВ", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)

    table = document.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = [
        "№ п/п", "Фамилия, имя, отчество", "Городской округ",
        "Квалификационная категория спортивного судьи", "Количество часов",
    ]
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(11)

    for i, lecturer in enumerate(lecturers, start=1):
        row = table.add_row().cells
        values = [
            str(i), lecturer.full_name or "", lecturer.region or "",
            lecturer.qualification or "", lecturer.lecture_hours or "",
        ]
        for cell, value in zip(row, values):
            cell.text = value
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.size = Pt(11)

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def polozhenie_filename(seminar):
    name = seminar.name or "семинар"
    return f"Положение {name}.docx"
