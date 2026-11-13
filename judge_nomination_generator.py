# judge_nomination_generator.py — «Представление к присвоению квалификационной
# категории спортивного судьи» в Word по данным карточки учёта судьи.
# Образец из data/ даёт параметры страницы, заголовок и блок подписей;
# строки с данными (левая половина — сведения о судье и теоретическая
# подготовка, правая — практика судейства) собираются заново, потому что
# число семинаров и соревнований у каждого судьи своё.
import copy
import os
import re
from datetime import date
from io import BytesIO

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import _Cell

import references
from judge_docx_generator import NBSP, normalize_document, normalize_text
from models import date_key

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "data", "Представление СС1К Серганов СА.docx")

# Ширины колонок сетки образца (dxa): 0–10 — левая половина, 11–14 — соревнования
GRID = [2552, 238, 612, 709, 808, 1913, 945, 619, 563, 36, 1017, 1188, 2287, 1203, 1470]
LEFT_LAST, RIGHT_FIRST, LAST = 10, 11, 14
PHOTO_BOX_EMU = (1207135, 1536065)
# Минимальные высоты строк (twips) как в образце; строки семинаров/соревнований — 330
ROW_HEIGHTS = {0: 608, 1: 114, **{i: 567 for i in range(2, 10)}, 10: 528}

NEXT_CATEGORY = {
    "Спортивный судья третьей категории": "Спортивный судья второй категории",
    "Спортивный судья второй категории": "Спортивный судья первой категории",
    "Спортивный судья первой категории": "Спортивный судья всероссийской категории",
    "Спортивный судья всероссийской категории": "Спортивный судья всероссийской категории",
}
CATEGORY_ABBR = {full: abbr for abbr, full in references.JUDGE_CATEGORY_ABBREVIATIONS.items()}

_RE_PARTS = re.compile(r"(\d{1,2}(?:\s*-\s*\d{1,2})?)\.\s*(\d{1,2})\.\s*(\d{4})")
_RE_ZACHET = re.compile(r"зач[её]т", re.IGNORECASE)
_RE_HOURS = re.compile(r"\d+\s*(?:академ\w*\s*)?час", re.IGNORECASE)
_RE_EKP = re.compile(r"(?<![А-Яа-яЁё])Е?КП(?![А-Яа-яЁё])")
_RE_POINTS = re.compile(r"балл", re.IGNORECASE)
NB_HYPHEN = "\u2011"  # маркер: в документ пишется как <w:noBreakHyphen/>
# «КП № 1378-СМ», «№ в ЕКП 29698», «ЕКП № 123» — номер не должен рваться по строкам
_RE_EKP_NUMBER = re.compile(r"(?:№\s*(?:в\s+)?)?(?<![А-Яа-яЁё])Е?КП(?![А-Яа-яЁё])\s*(?:№\s*)?\d[\w/-]*")
MARK_FILL = "FFFF00"  # жёлтая заливка: в карточке не заполнены данные для этой ячейки


# --- Разбор данных карточки ---

def _date_parts(text):
    """«11-12.11. 2023» -> ('11-12', '11', '2023')."""
    m = _RE_PARTS.search(text or "")
    if m:
        return tuple(re.sub(r"\s+", "", g) for g in m.groups())
    return (text or "").strip(), "", ""


def _is_filled(value):
    return bool(value and value.strip() and value.strip() != "-")


def _hours(score):
    m = re.search(r"\d+", score or "")
    if not m:
        return None
    n = int(m.group())
    return f"{n}-х" if n in (2, 3, 4) else str(n)


def _grade(score):
    """Оценка без объёма часов: «2 часа, зачет» -> «Зачёт»."""
    if not score:
        return ""
    if _RE_ZACHET.search(score):
        return "Зачёт"
    parts = [p.strip() for p in score.split(",") if p.strip() and not _RE_HOURS.search(p)]
    tail = parts[-1] if parts else ""
    return tail[:1].upper() + tail[1:]


# Уровни образования, длинные варианты раньше коротких («неоконченное высшее» до «высшее»)
EDUCATION_LEVELS = [
    "Неоконченное высшее", "Незаконченное высшее", "Высшее",
    "Среднее профессиональное", "Среднее специальное", "Среднее техническое",
    "Начальное профессиональное", "Среднее общее", "Основное общее", "Среднее",
]


def _education_level(text):
    """Только уровень образования без учебного заведения; второй элемент —
    распознан ли уровень (иначе ячейка помечается)."""
    t = (text or "").strip()
    low = t.lower()
    for level in EDUCATION_LEVELS:
        if low.startswith(level.lower()) or re.search(rf"(?<![а-яё]){level.lower()}(?![а-яё])", low):
            return level, True
    return re.split(r"[,(]", t)[0].strip(), False


def _document_text(text):
    text = normalize_text(text)
    return _RE_EKP_NUMBER.sub(lambda m: re.sub(r"\s+", NBSP, m.group()).replace("-", NB_HYPHEN), text)


def _append_text(r, text):
    """Текст в run; маркеры NB_HYPHEN становятся неразрывными дефисами Word."""
    for i, piece in enumerate(text.split(NB_HYPHEN)):
        if i:
            r.append(OxmlElement("w:noBreakHyphen"))
        if piece:
            t = OxmlElement("w:t")
            t.set(qn("xml:space"), "preserve")
            t.text = piece
            r.append(t)


def _initials(judge):
    return "".join(p[0] for p in (judge.first_name, judge.middle_name) if p)


# --- Построение ячеек таблицы ---

def _border(parent, side, val):
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), val)
    el.set(qn("w:sz"), "4")
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), "auto")
    parent.append(el)


def _shd(fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    return shd


def _mark_tc(tc):
    tc.find(qn("w:tcPr")).find(qn("w:tcBorders")).addnext(_shd(MARK_FILL))


_PPR_BEFORE_SHD = {qn(t) for t in ("w:pStyle", "w:keepNext", "w:keepLines", "w:pageBreakBefore", "w:framePr",
                                     "w:widowControl", "w:numPr", "w:suppressLineNumbers", "w:pBdr")}


def _mark_p(p):
    """Пометка строки в блоке подписей (заливка абзаца видна и у пустого)."""
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p.insert(0, ppr)
    before = [c for c in ppr if c.tag in _PPR_BEFORE_SHD]
    if before:
        before[-1].addnext(_shd(MARK_FILL))
    else:
        ppr.insert(0, _shd(MARK_FILL))


def _make_tc(start, span, text="", pt=8, bold=False, align="center", vmerge=None, top_double=False, mark=False):
    tc = OxmlElement("w:tc")
    pr = OxmlElement("w:tcPr")
    tc.append(pr)

    tcw = OxmlElement("w:tcW")
    tcw.set(qn("w:w"), str(sum(GRID[start:start + span])))
    tcw.set(qn("w:type"), "dxa")
    pr.append(tcw)
    if span > 1:
        gs = OxmlElement("w:gridSpan")
        gs.set(qn("w:val"), str(span))
        pr.append(gs)
    if vmerge:
        vm = OxmlElement("w:vMerge")
        if vmerge == "restart":
            vm.set(qn("w:val"), "restart")
        pr.append(vm)

    end = start + span - 1
    borders = OxmlElement("w:tcBorders")
    _border(borders, "top", "double" if top_double else "single")
    _border(borders, "left", "double" if start in (0, RIGHT_FIRST) else "single")
    _border(borders, "bottom", "single")
    _border(borders, "right", "double" if end in (LEFT_LAST, LAST) else "single")
    pr.append(borders)
    if mark:
        pr.append(_shd(MARK_FILL))

    mar = OxmlElement("w:tcMar")
    for side in ("left", "right"):
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), "28")
        m.set(qn("w:type"), "dxa")
        mar.append(m)
    pr.append(mar)
    va = OxmlElement("w:vAlign")
    va.set(qn("w:val"), "center")
    pr.append(va)

    lines = (text or "").split("\n") if vmerge != "cont" else [""]
    for line in lines:
        tc.append(_make_p(line, pt, bold, align))
    return tc


def _make_rpr(pt, bold):
    rpr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for attr in ("ascii", "hAnsi", "cs"):
        fonts.set(qn(f"w:{attr}"), "Times New Roman")
    rpr.append(fonts)
    if bold:
        rpr.append(OxmlElement("w:b"))
    for tag in ("w:sz", "w:szCs"):
        sz = OxmlElement(tag)
        sz.set(qn("w:val"), str(int(pt * 2)))
        rpr.append(sz)
    return rpr


def _make_p(text, pt, bold, align):
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "240")
    spacing.set(qn("w:lineRule"), "auto")
    ppr.append(spacing)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), align)
    ppr.append(jc)
    ppr.append(_make_rpr(pt, bold))
    p.append(ppr)
    if text:
        r = OxmlElement("w:r")
        r.append(_make_rpr(pt, bold))
        _append_text(r, _document_text(text))
        p.append(r)
    return p


def _make_tr(height=None):
    tr = OxmlElement("w:tr")
    trpr = OxmlElement("w:trPr")
    if height:
        h = OxmlElement("w:trHeight")
        h.set(qn("w:val"), str(height))
        h.set(qn("w:hRule"), "atLeast")
        trpr.append(h)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    trpr.append(jc)
    tr.append(trpr)
    return tr


def C(start, span, text="", pt=8, bold=False, align="center", vm=None, need=False, mark=False):
    """need — обязательные данные: пустая ячейка помечается заливкой;
    mark — пометить заливкой независимо от текста (данные неполные)."""
    mark = mark or (need and not (text or "").strip())
    return dict(start=start, span=span, text=text, pt=pt, bold=bold, align=align, vm=vm, mark=mark)


# --- Содержимое левой и правой половины ---

def _left_rows(judge, settings, subject, current, previous_date):
    birth = judge.birth_date
    prev = previous_date
    org = ",\n".join(x for x in (
        subject.organization_name if subject else "", subject.organization_address if subject else "",
    ) if x)
    education, education_known = _education_level(judge.education)
    rows = [
        [C(0, 1, "Дата поступления представления и документов\n(число, месяц, год)", vm="restart"),
         C(1, 2, vm="restart"), C(3, 1, vm="restart"), C(4, 1, vm="restart"),
         C(5, 1, vm="restart"),
         C(6, 5, "Наименование действующей квалификационной категории\nспортивного судьи")],
        [C(0, 1, vm="cont"), C(1, 2, vm="cont"), C(3, 1, vm="cont"), C(4, 1, vm="cont"),
         C(5, 1, vm="cont"),
         C(6, 5, (current or "").replace("судья ", "судья\n", 1), pt=11, need=True)],
        [C(0, 1, "Фамилия"), C(1, 4, judge.last_name, pt=12, need=True), C(5, 1, vm="cont"),
         C(6, 5, "Дата присвоения предыдущей квалификационной категории\nспортивного судьи\n"
                 "(число, месяц, год)", vm="restart")],
        [C(0, 1, "Имя"), C(1, 4, judge.first_name, pt=12, need=True), C(5, 1, vm="cont"), C(6, 5, vm="cont")],
        [C(0, 1, "Отчество (при наличии)"), C(1, 4, judge.middle_name or "", pt=12), C(5, 1, vm="cont"),
         C(6, 1, prev.strftime("%d") if prev else "", pt=12, need=True),
         C(7, 2, prev.strftime("%m") if prev else "", pt=12, need=True),
         C(9, 2, prev.strftime("%Y") if prev else "", pt=12, need=True)],
        [C(0, 1, "Дата рождения\n(число, месяц, год)"),
         C(1, 2, birth.strftime("%d") if birth else "", pt=12, need=True),
         C(3, 1, birth.strftime("%m") if birth else "", pt=12, need=True),
         C(4, 1, birth.strftime("%Y") if birth else "", pt=12, need=True),
         C(5, 1, "Наименование вида спорта (спортивной дисциплины)"),
         C(6, 5, settings.sport_name if settings else "", pt=12, need=True)],
        [C(0, 1, "Субъект Российской Федерации"), C(1, 4, judge.region or "", pt=12, need=True),
         C(5, 1, "Номер-код вида спорта"), C(6, 5, settings.sport_code if settings else "", pt=12, need=True)],
        [C(0, 1, "Адрес (место жительства)"), C(1, 4, judge.address or "", need=True),
         C(5, 1, "Наименование и адрес (место нахождения) организации, осуществляющей учет "
                 "судейской деятельности спортивного судьи", pt=7.5, vm="restart"),
         C(6, 5, org, vm="restart", need=True)],
        [C(0, 1, "Место работы (учебы), должность"), C(1, 4, judge.workplace or "", pt=6.5, need=True),
         C(5, 1, vm="cont"), C(6, 5, vm="cont")],
        [C(0, 1, "Образование"), C(1, 4, education, pt=12, mark=not education_known),
         C(5, 1, "Спортивное звание"), C(6, 5, judge.rank or "", pt=12)],
        [C(0, 6, "Участие в теоретических занятиях, сдача нормативов по физической подготовке "
                 "(для видов спорта, где такие нормативы предусмотрены правилами вида спорта), "
                 "сдача квалификационного зачета, прохождение аттестации", pt=7),
         C(6, 4, "Дата (число, месяц, год)"), C(10, 1, "Оценка")],
    ]

    seminars = sorted(
        (r for r in judge.training_records if r.included_in_nomination),
        key=lambda r: date_key(r.seminar_date) or (0, 0, 0),
    )
    n = 0
    for rec in seminars:
        activities = []
        if _is_filled(rec.participant_score) or _is_filled(rec.participant_category):
            hours = _hours(rec.participant_score)
            volume = f" в объеме {hours} академических часов" if hours else ""
            activities.append((f"Теоретическая подготовка{volume} в форме семинара", not hours,
                               rec.seminar_date, _grade(rec.participant_score)))
        if _is_filled(rec.lecturer_score) or _is_filled(rec.lecturer_category):
            hours = _hours(rec.lecturer_score)
            volume = f" в объеме {hours} академических часов" if hours else ""
            # participant_date хранит дату занятий в качестве лектора (колонка
            # «Дата» под группой «Лектор» в образце карточки, см. judge_docx_importer)
            activities.append((f"Проведение теоретических занятий{volume} в форме семинара", not hours,
                               rec.participant_date or rec.seminar_date, _grade(rec.lecturer_score)))
        if not activities:
            continue
        n += 1
        title = f"{n}. {rec.seminar_name or ''}" + (f", {rec.location}" if rec.location else "")
        for i, (activity, no_hours, when, grade) in enumerate(activities):
            d, m, y = _date_parts(when)
            rows.append([
                C(0, 2, title, pt=6, align="left", vm=("restart" if i == 0 else "cont"),
                  mark=(i == 0 and not (rec.seminar_name and rec.location))),
                C(2, 4, activity, pt=6, align="left", mark=no_hours),
                C(6, 1, d, pt=10, need=True), C(7, 1, m, pt=10, need=True), C(8, 2, y, pt=10, need=True),
                C(10, 1, grade, pt=10, need=True),
            ])

    exams = [r for r in seminars if _is_filled(r.exam_score)]
    if exams:
        rec = exams[-1]
        n += 1
        title = f"{n}. Сдача квалификационного зачёта “Нормативные документы по виду спорта”"
        if rec.location:
            title += f", {rec.location}"
        # lecturer_date хранит дату сдачи зачёта (в форме — «Дата (зачёт)»)
        d, m, y = _date_parts(rec.lecturer_date)
        rows.append([C(0, 6, title, pt=6, align="left", mark=not rec.location),
                     C(6, 1, d, pt=10, need=True), C(7, 1, m, pt=10, need=True), C(8, 2, y, pt=10, need=True),
                     C(10, 1, _grade(rec.exam_score), pt=10, need=True)])
    return rows


def _right_rows(judge):
    rows = [
        [C(11, 1, "Сроки проведения официального соревнования\n(с дд/мм/гг до дд/мм/гг)", vm="restart"),
         C(12, 1, "Наименование официального соревнования", vm="restart"),
         C(13, 1, "Статус официального соревнования", vm="restart"),
         C(14, 1, "Наименование должности спортивного судьи\nи оценка судейства", vm="restart")],
        [C(c, 1, vm="cont") for c in range(11, 15)],
    ]
    for rec in judge.sorted_competition_records:
        if not rec.included_in_nomination:
            continue
        # № в ЕКП / КП записывается в наименовании, баллы — вместе с оценкой
        name = (rec.competition_name or "").strip()
        position_name = (rec.judge_position or "").strip()
        score = (rec.score or "").strip()
        position = ", ".join(x for x in (position_name, score[:1].lower() + score[1:]) if x)
        rows.append([
            C(11, 1, rec.event_date or "", pt=8, need=True),
            C(12, 1, name, pt=6.5, mark=not (name and _RE_EKP.search(name))),
            C(13, 1, rec.competition_status or "", pt=6.5, need=True),
            C(14, 1, position, pt=6.5, mark=not (position_name and score and _RE_POINTS.search(score))),
        ])
    return rows


# --- Сборка документа ---

def _set_para_text(p, text):
    runs = p.findall(qn("w:r"))
    rpr = copy.deepcopy(runs[0].find(qn("w:rPr"))) if runs and runs[0].find(qn("w:rPr")) is not None else None
    for r in runs:
        p.remove(r)
    if not text:
        return
    r = OxmlElement("w:r")
    if rpr is not None:
        r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    p.append(r)


def _fill_title(tr, target):
    p = tr.find(qn("w:tc")).find(qn("w:p"))
    runs = p.findall(qn("w:r"))
    runs[1].find(qn("w:t")).text = (target or "").upper()
    for r in runs[2:]:
        p.remove(r)


def _fill_signature(tr, subject):
    tc = tr.find(qn("w:tc"))
    paras = tc.findall(qn("w:p"))
    org = (subject.organization_name if subject else "") or ""
    head, sep, tail = org.partition("«")
    _set_para_text(paras[0], head.strip() if sep else org)
    _set_para_text(paras[1], (sep + tail).strip() if sep else "")
    if not org:
        _mark_p(paras[0])
    position = (subject.organization_leader_position if subject else "") or ""
    leader = (subject.organization_leader_name if subject else "") or ""
    _set_para_text(paras[7], f"     {position:<38}        {leader}" if (position or leader) else "")
    if not (position and leader):
        _mark_p(paras[7])
    # Строка «Дата ___ Подпись ___»: дата образца разбита на несколько
    # подчёркнутых runs — меняем только цифры, чтобы сохранить подчёркивание
    today = f"{date.today():%d.%m.%Y}"
    placed = False
    for t in paras[10].iter(qn("w:t")):
        if "Подпись" in (t.text or ""):
            break
        m = re.search(r"[\d.]", t.text or "")
        if m:
            rest = re.sub(r"[\d.]", "", t.text[m.start():])
            t.text = t.text[:m.start()] + ("" if placed else today) + rest
            placed = True


def _add_photo(table, tr, judge):
    filename = getattr(judge, "photo_filename", None)
    path = os.path.join(BASE_DIR, "static", "uploads", "judges", filename) if filename else None
    tc = tr.findall(qn("w:tc"))[4]
    if not path or not os.path.exists(path):
        _mark_tc(tc)
        return
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
        scale = min(PHOTO_BOX_EMU[0] / w, PHOTO_BOX_EMU[1] / h)
        _Cell(tc, table).paragraphs[0].add_run().add_picture(path, width=int(w * scale), height=int(h * scale))
    except Exception as e:
        import sys
        print(f"[nomination photo] error: {e}", file=sys.stderr)


def _shrink_trailing_paragraph(tbl):
    """Обязательный пустой абзац после таблицы на всю страницу иначе
    переносится на отдельный пустой лист."""
    p = tbl.getnext()
    if p is None or p.tag != qn("w:p"):
        return
    for child in list(p):
        p.remove(child)
    ppr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "20")
    spacing.set(qn("w:lineRule"), "exact")
    ppr.append(spacing)
    ppr.append(_make_rpr(1, False))
    p.append(ppr)


def generate_nomination(judge, settings, subject):
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    tbl = table._tbl
    trs = tbl.findall(qn("w:tr"))
    title_tr, signature_tr = trs[0], trs[-1]
    for tr in trs[1:-1]:
        tbl.remove(tr)
    # Фото образца лежит в удалённой строке; убираем осиротевшие связи с картинками
    for rel_id, rel in list(document.part.rels.items()):
        if rel.reltype.endswith("/image"):
            document.part.drop_rel(rel_id)

    current = judge.current_category
    target = NEXT_CATEGORY.get(current, references.JUDGE_CATEGORIES[-1])
    previous_date = judge.previous_category_date

    _fill_title(title_tr, target)
    left = _left_rows(judge, settings, subject, current, previous_date)
    right = _right_rows(judge)

    total = max(len(left), len(right))
    while len(right) < total:
        right.append([C(c, 1) for c in range(11, 15)])
    if len(left) < total:
        pad = total - len(left)
        left += [[C(0, LEFT_LAST + 1, vm=("restart" if i == 0 else "cont"))] for i in range(pad)]

    new_trs = []
    for i in range(total):
        tr = _make_tr(height=ROW_HEIGHTS.get(i, 330))
        for spec in left[i] + right[i]:
            tr.append(_make_tc(spec["start"], spec["span"], spec["text"], spec["pt"], spec["bold"],
                               spec["align"], spec["vm"], top_double=(i == 0), mark=spec["mark"]))
        signature_tr.addprevious(tr)
        new_trs.append(tr)

    _fill_signature(signature_tr, subject)
    _add_photo(table, new_trs[0], judge)
    _shrink_trailing_paragraph(tbl)
    normalize_document(document)

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def nomination_filename(judge):
    current = judge.current_category
    target = NEXT_CATEGORY.get(current, references.JUDGE_CATEGORIES[-1])
    parts = ["Представление", CATEGORY_ABBR.get(target, ""), judge.last_name, _initials(judge)]
    return " ".join(p for p in parts if p) + ".docx"
