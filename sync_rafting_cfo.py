# sync_rafting_cfo.py — отправка семинара на сайт RAFTING_CFO
#
# Сайт (rafting_cfo, отдельный Flask-проект) принимает мероприятия через
# POST /api/sync/events с заголовком X-API-Key (см. его routes/api.py).
# Адрес сайта и ключ берутся из .env — RAFTING_CFO_URL / RAFTING_CFO_API_KEY,
# ключ должен совпадать с API_KEY в .env самого сайта.
#
# У семинара здесь нет отдельного поля "дата окончания" — только start_date
# (структурированная) и period (свободный текст вида "09-10.11.2019г."
# или "9 - 10 ноября 2025"). Дату окончания пытаемся вытащить из этого
# текста; не получилось — считаем семинар однодневным. Этот проект ведёт
# только семинары подготовки судей, поэтому event_type всегда 'семинар_судей'.
import os
import re
from datetime import date as _date

import requests

RAFTING_CFO_URL = os.environ.get('RAFTING_CFO_URL', 'http://127.0.0.1:5003').rstrip('/')
RAFTING_CFO_API_KEY = os.environ.get('RAFTING_CFO_API_KEY', '')

RU_MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
}
# Числовой формат "DD.MM.YYYY" (со сдвигом ошибки в 1 год пренебрегаем —
# в period встречается и он, и словесный "DD месяц [YYYY]").
_ДАТА_ЧИСЛОМ_RE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')
_ДАТА_СЛОВОМ_RE = re.compile(r'(\d{1,2})\s+(' + '|'.join(RU_MONTHS) + r')(?:\s+(\d{4}))?')


def _распознать_дату_окончания(текст, год_по_умолчанию):
    """Последнее совпадение даты в свободном тексте period — это и есть
    дата окончания при формате "9 - 10 ноября 2025" или "09-10.11.2019г.".
    Не найдено — None."""
    if not текст:
        return None

    числом = list(_ДАТА_ЧИСЛОМ_RE.finditer(текст))
    if числом:
        день, месяц, год = (int(g) for g in числом[-1].groups())
        try:
            return _date(год, месяц, день)
        except ValueError:
            return None

    словом = list(_ДАТА_СЛОВОМ_RE.finditer(текст))
    if словом:
        последнее = словом[-1]
        день = int(последнее.group(1))
        месяц = RU_MONTHS[последнее.group(2)]
        год = int(последнее.group(3)) if последнее.group(3) else год_по_умолчанию
        try:
            return _date(год, месяц, день)
        except ValueError:
            return None

    return None


def _определить_статус(начало, окончание):
    сегодня = _date.today()
    конец = окончание or начало
    if сегодня < начало:
        return 'анонс'
    if сегодня > конец:
        return 'завершён'
    return 'идёт'


def собрать_данные(семинар):
    """Строит словарь одного элемента для POST /api/sync/events."""
    окончание = _распознать_дату_окончания(семинар.period, семинар.start_date.year)
    return {
        'source_id': семинар.id,
        'name': семинар.name,
        'event_type': 'семинар_судей',
        'start_date': семинар.start_date.isoformat(),
        'end_date': окончание.isoformat() if окончание else None,
        'location': семинар.location,
        'status': _определить_статус(семинар.start_date, окончание),
    }


def отправить_на_сайт(семинар):
    """Отправляет один семинар на сайт. Возвращает (успех, сообщение)."""
    if not RAFTING_CFO_API_KEY:
        return False, 'RAFTING_CFO_API_KEY не задан в .env — см. .env.example'
    if not семинар.start_date:
        return False, 'У семинара не заполнена дата начала — заполните на странице редактирования'

    try:
        ответ = requests.post(
            f'{RAFTING_CFO_URL}/api/sync/events',
            json={'items': [собрать_данные(семинар)]},
            headers={'X-API-Key': RAFTING_CFO_API_KEY},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с сайтом ({RAFTING_CFO_URL}): {exc}'

    if ответ.status_code != 200:
        return False, f'Сайт ответил ошибкой {ответ.status_code}: {ответ.text[:200]}'

    данные = ответ.json()
    if данные.get('errors'):
        return False, '; '.join(данные['errors'])
    return True, 'Отправлено на сайт.'
