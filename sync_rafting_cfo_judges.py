# sync_rafting_cfo_judges.py — отправка спортивных судей на сайт RAFTING_CFO
#
# Отдельно от sync_rafting_cfo.py (тот отправляет семинары и заявки на
# семинары) — здесь отправляются сами карточки судей, чтобы на сайте они
# появились в разделе «Спортивные судьи» на странице региональной
# федерации (сопоставление там идёт по совпадению territory с
# наименованием субъекта РФ этой федерации — см. RAFTING_CFO
# routes/regions.py.section()).
#
# Judge.region в этой базе — уже наименование субъекта РФ (в отличие от
# REGTEAM_RAFTING, где Athlete.territory — внутренний район и субъект РФ
# берётся из отдельной настройки .env), поэтому дополнительная per-инстанс
# переменная окружения тут не нужна: судья сам знает свой регион.
#
# Отправка НЕ автоматическая — по кнопке (routes/judges.py): либо одного
# судьи с его карточки, либо всех разом со страницы списка (нужно, чтобы
# на сайт попали и включения, и исключения из активного списка — одной
# кнопкой на карточке легко упустить кого-то). Ошибка отправки не должна
# ломать сохранение в локальной базе — сторонняя система, локальная база
# остаётся источником истины независимо от доступности сайта.
#
# Адрес и ключ — RAFTING_CFO_URL / RAFTING_CFO_API_KEY в .env (общие с
# sync_rafting_cfo.py); значения читаются из os.environ при каждом
# вызове (не на уровне модуля), чтобы правка .env не требовала полного
# перезапуска процесса.
import os

import requests

import references

# То же сокращение, что и в app.py (фильтр category_abbr) — на сайт
# категория уходит уже в виде ССВК/СС1К/СС2К/СС3К, полным написанием
# сайт её не показывает.
_КАТЕГОРИЯ_В_СОКРАЩЕНИЕ = {full: abbr for abbr, full in references.JUDGE_CATEGORY_ABBREVIATIONS.items()}


def _адрес():
    return os.environ.get('RAFTING_CFO_URL', 'http://127.0.0.1:5003').rstrip('/')


def _ключ():
    return os.environ.get('RAFTING_CFO_API_KEY', '')


def _собрать_данные(judge):
    return {
        'source_id': judge.id,
        'full_name': judge.full_name,
        'category': _КАТЕГОРИЯ_В_СОКРАЩЕНИЕ.get(judge.current_category, judge.current_category),
        'disciplines': judge.discipline_group,
        'territory': judge.region,
        'organization': judge.workplace,
        'municipality': judge.municipality,
        'specialization': judge.specialization,
        'is_active': bool(judge.is_active),
    }


def _отправить(items):
    """Общая отправка POST {"items": [...]} на /api/sync/referees. Возвращает
    (успех, сообщение) — используется и для upsert, и для удаления."""
    ключ = _ключ()
    if not ключ:
        return False, 'RAFTING_CFO_API_KEY не задан в .env — см. .env.example'

    адрес = _адрес()
    try:
        ответ = requests.post(
            f'{адрес}/api/sync/referees',
            json={'items': items},
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с RAFTING_CFO ({адрес}): {exc}'

    if ответ.status_code == 401:
        return False, 'RAFTING_CFO отклонил запрос: неверный RAFTING_CFO_API_KEY.'
    if ответ.status_code != 200:
        return False, f'RAFTING_CFO ответил ошибкой {ответ.status_code}: {ответ.text[:200]}'

    return True, 'Отправлено на RAFTING_CFO.'


def отправить_судью(judge):
    """Отправляет ОДНОГО судью на RAFTING_CFO (создание или обновление —
    сторона RAFTING_CFO определяет это сама по source_id). Возвращает
    (успех, сообщение)."""
    return _отправить([_собрать_данные(judge)])


def отправить_всех(judges):
    """Отправляет ВЕСЬ текущий список судей одним запросом (кнопка
    «Отправить всех на сайт» на странице списка) — так на сайт
    гарантированно попадают и включения, и исключения из активного
    списка, даже если кто-то не был отправлен по отдельности. judges —
    итерируемое Judge (обычно Judge.query.all(), включая is_active=False
    — сторона RAFTING_CFO сама решает, где кого показывать). Возвращает
    (успех, сообщение)."""
    items = [_собрать_данные(judge) for judge in judges]
    if not items:
        return True, 'Список пуст — отправлять нечего.'
    return _отправить(items)


def удалить_судью(judge_id):
    """Удаляет судью на RAFTING_CFO по source_id (вызывать ПОСЛЕ
    judges_delete — для исключения из активного списка без удаления
    записи используется отправить_судью с is_active=False, эта функция —
    только для настоящего удаления записи)."""
    return _отправить([{'source_id': judge_id, 'deleted': True}])
