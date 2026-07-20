# seminar_polozhenie_generator.py — генерация документа «Положение о семинаре»
# в точном соответствии оформлению образца data/Положение семинар СС1К.doc
# (шрифт Times New Roman 12пт, поля страницы, выравнивание, отступ первой строки,
# центрированные полужирные заголовки разделов, порядок разделов).
from io import BytesIO

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from models import Settings

SEMINAR_CATEGORY_GENITIVE = {
    "Всероссийская": "всероссийской",
    "Первая": "первой",
    "Вторая": "второй",
    "Третья": "третьей",
    "Юный судья": "«Юный судья»",
}

# Значение поля «Количество часов» -> согласованная форма перед словом «программе»
PROGRAM_HOURS_ADJECTIVE = {
    "16-ти часовая": "16-ти часовой",
    "12-ти часовая": "12-ти часовой",
    "10-тичасовая": "10-ти часовой",
}


def _fmt_date(value):
    return value.strftime("%d.%m.%Y") if value else ""


def build_polozhenie_data(seminar, lecturers):
    """Собирает содержимое положения о семинаре из полей формы — единый источник
    данных и для страницы печати в браузере, и для генерации .docx."""
    settings = Settings.query.first()
    sport_name = settings.sport_name if settings and settings.sport_name else "рафтинг"
    category_genitive = SEMINAR_CATEGORY_GENITIVE.get(seminar.category, "")

    title_sub = (
        f"о региональном семинаре по подготовке и повышению квалификации "
        f"спортивных судей {category_genitive} категории по виду спорта «{sport_name}»"
    ).replace("  ", " ").strip()

    # 1. Спортивная федерация по рафтингу
    section1 = []
    full_name = seminar.polozhenie_federation_full_name or ""
    short_name = seminar.polozhenie_federation_short_name or ""
    if full_name:
        line = f"Организатором семинара является {full_name}"
        if short_name:
            line += f" (далее по тексту — {short_name})"
        section1.append(line + ".")
    if seminar.polozhenie_federation_region:
        section1.append(f"Субъект Российской Федерации: {seminar.polozhenie_federation_region}.")
    if seminar.polozhenie_federation_leader_position or seminar.polozhenie_federation_leader_name:
        line = "Руководитель"
        if short_name:
            line += f" {short_name}"
        line += " —"
        if seminar.polozhenie_federation_leader_position:
            line += f" {seminar.polozhenie_federation_leader_position},"
        if seminar.polozhenie_federation_leader_name:
            line += f" {seminar.polozhenie_federation_leader_name}"
        section1.append(line.rstrip(",") + ".")
    if seminar.polozhenie_federation_phone or seminar.polozhenie_federation_email:
        parts = []
        if seminar.polozhenie_federation_phone:
            parts.append(f"тел. {seminar.polozhenie_federation_phone}")
        if seminar.polozhenie_federation_email:
            parts.append(f"эл. почта: {seminar.polozhenie_federation_email}")
        section1.append(", ".join(parts).capitalize() + ".")

    # 2. Сроки и место проведения семинара
    section2 = []
    if seminar.polozhenie_period:
        section2.append(f"2.1. Сроки проведения семинара: {seminar.polozhenie_period}.")
    if seminar.polozhenie_location:
        section2.append(f"2.2. Место проведения семинара: {seminar.polozhenie_location}.")

    # 3. Программа
    section3 = []
    hours_value = seminar.polozhenie_program_hours or ""
    hours_adj = PROGRAM_HOURS_ADJECTIVE.get(hours_value, hours_value)
    if hours_value:
        section3.append(
            f"3.1. Теоретические занятия по подготовке спортивных судей {category_genitive} категории "
            f"проводятся в форме семинара и практических занятий по {hours_adj} программе."
        )
    if seminar.qualification_exam == "Да":
        section3.append(
            "3.2. Квалификационный зачёт для присвоения (подтверждения) квалификационной категории "
            "спортивного судьи проводится в форме экзамена по тестовым вопросам."
        )

    # 4. Размер заявочного взноса за участие
    section4 = []
    if seminar.polozhenie_fee_amount:
        section4.append(f"Размер: {seminar.polozhenie_fee_amount}.")
    if seminar.polozhenie_fee_requisites:
        section4.append(f"Реквизиты для оплаты: {seminar.polozhenie_fee_requisites}.")
    if seminar.polozhenie_fee_purpose:
        section4.append(f"Назначение платежа: {seminar.polozhenie_fee_purpose}.")

    # 5. Варианты проживания и питания участников
    section5 = [line for line in (seminar.polozhenie_accommodation or "").split("\n") if line.strip()]

    # 6. Проезд до места проведения
    section6 = [line for line in (seminar.polozhenie_travel or "").split("\n") if line.strip()]

    # 7. Заявки на участие
    section7 = []
    if seminar.polozhenie_applications_deadline:
        section7.append(
            f"Для участия в семинаре необходимо подать заявку до {_fmt_date(seminar.polozhenie_applications_deadline)} "
            f"включительно."
        )
    if seminar.polozhenie_applications_email:
        section7.append(f"По электронной почте: {seminar.polozhenie_applications_email}.")
    if seminar.polozhenie_applications_contacts:
        section7.append(f"Контакты организаторов: {seminar.polozhenie_applications_contacts}.")

    sections = [
        (1, "Спортивная федерация по рафтингу", section1),
        (2, "Сроки и место проведения семинара", section2),
        (3, "Программа", section3),
        (4, "Размер заявочного взноса за участие", section4),
        (5, "Варианты проживания и питания участников", section5),
        (6, "Проезд до места проведения", section6),
        (7, "Заявки на участие", section7),
    ]

    return {
        "approver_position": seminar.polozhenie_federation_leader_position or "",
        "approver_name": seminar.polozhenie_federation_leader_name or "",
        "title_sub": title_sub,
        "sections": sections,
        "closing": "Данное положение является приглашением на семинар",
        "lecturers": lecturers,
    }


def _add_paragraph(document, text="", bold=False, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
                    first_line_indent=None, space_after=0):
    p = document.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    if first_line_indent is not None:
        p.paragraph_format.first_line_indent = Cm(first_line_indent)
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    return p


def generate_polozhenie(seminar, lecturers):
    data = build_polozhenie_data(seminar, lecturers)
    document = docx.Document()

    style = document.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    section = document.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(1.25)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)

    _add_paragraph(document, "УТВЕРЖДАЮ", align=WD_ALIGN_PARAGRAPH.RIGHT)
    if data["approver_position"]:
        _add_paragraph(document, data["approver_position"], align=WD_ALIGN_PARAGRAPH.RIGHT)
    _add_paragraph(document, "")
    _add_paragraph(document, f"_______________ {data['approver_name']}".rstrip(), align=WD_ALIGN_PARAGRAPH.RIGHT)
    _add_paragraph(document, "")

    _add_paragraph(document, "ПОЛОЖЕНИЕ", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_paragraph(document, data["title_sub"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_paragraph(document, "")

    for number, heading, paragraphs in data["sections"]:
        _add_paragraph(document, f"{number}. {heading}", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        for line in paragraphs:
            _add_paragraph(document, line, first_line_indent=1.25)
        if not paragraphs:
            _add_paragraph(document, "")
        _add_paragraph(document, "")

    _add_paragraph(document, data["closing"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

    if lecturers:
        document.add_page_break()
        _add_paragraph(document, "Приложение 1", align=WD_ALIGN_PARAGRAPH.RIGHT)
        _add_paragraph(document, f"к положению {data['title_sub']}", align=WD_ALIGN_PARAGRAPH.RIGHT)
        _add_paragraph(document, "")
        _add_paragraph(document, "ПРЕПОДАВАТЕЛЬСКИЙ СОСТАВ", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

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
                    run.font.name = "Times New Roman"
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
                        run.font.name = "Times New Roman"
                        run.font.size = Pt(11)

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def polozhenie_filename(seminar):
    name = seminar.name or "семинар"
    return f"Положение {name}.docx"
