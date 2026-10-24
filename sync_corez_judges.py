# sync_corez_judges.py — добавление судей в судейские коллегии соревнований COREZ
#
# В отличие от RAFTING_CFO (один плоский список судей региона), в COREZ
# судья — запись ПЕР СОРЕВНОВАНИЕ (своя строка в судейской коллегии
# каждого соревнования, с должностью на этом конкретном соревновании).
# Поэтому отправка не одной кнопкой на всех — с карточки судьи (routes/
# judges.py) сначала запрашивается список соревнований COREZ (GET
# /api/competitions), пользователь выбирает нужное и указывает должность,
# и только тогда судья уходит в его коллегию (POST .../judges). Сопоставление
# при повторной отправке — на стороне COREZ, по (соревнование_id, source_id
# = Judge.id в этой базе), так что повторная отправка обновляет запись, а
# не дублирует её.
#
# Адрес и ключ — COREZ_URL / COREZ_API_KEY в .env; читаются из os.environ
# при каждом вызове (не на уровне модуля), чтобы правка .env не требовала
# полного перезапуска процесса.
import os

import requests

import references

_КАТЕГОРИЯ_В_СОКРАЩЕНИЕ = {full: abbr for abbr, full in references.JUDGE_CATEGORY_ABBREVIATIONS.items()}


def _адрес():
    return os.environ.get('COREZ_URL', 'http://127.0.0.1:5000').rstrip('/')


def _ключ():
    return os.environ.get('COREZ_API_KEY', '')


def список_соревнований():
    """Запрашивает список соревнований COREZ для выбора на карточке судьи.
    Возвращает (успех, items_или_сообщение_об_ошибке)."""
    ключ = _ключ()
    if not ключ:
        return False, 'COREZ_API_KEY не задан в .env — см. .env.example'

    адрес = _адрес()
    try:
        ответ = requests.get(
            f'{адрес}/api/competitions',
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с COREZ ({адрес}): {exc}'

    if ответ.status_code == 401:
        return False, 'COREZ отклонил запрос: неверный COREZ_API_KEY.'
    if ответ.status_code != 200:
        return False, f'COREZ ответил ошибкой {ответ.status_code}: {ответ.text[:200]}'

    return True, ответ.json().get('items', [])


def добавить_в_коллегию(judge, соревнование_id, должность):
    """Добавляет/обновляет ОДНОГО судью в судейской коллегии соревнования
    соревнование_id с указанной должностью. Возвращает (успех, сообщение)."""
    ключ = _ключ()
    if not ключ:
        return False, 'COREZ_API_KEY не задан в .env — см. .env.example'

    item = {
        'source_id': judge.id,
        'фамилия_имя_отчество': judge.full_name,
        'квалификация': _КАТЕГОРИЯ_В_СОКРАЩЕНИЕ.get(judge.current_category, judge.current_category),
        'субъект_рф': judge.region,
        'дата_рождения': judge.birth_date.isoformat() if judge.birth_date else None,
        'действующая_категория': bool(judge.is_active),
        'должность': должность,
    }

    адрес = _адрес()
    try:
        ответ = requests.post(
            f'{адрес}/api/competitions/{соревнование_id}/judges',
            json={'items': [item]},
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с COREZ ({адрес}): {exc}'

    if ответ.status_code == 401:
        return False, 'COREZ отклонил запрос: неверный COREZ_API_KEY.'
    if ответ.status_code == 404:
        return False, 'Соревнование не найдено в COREZ.'
    if ответ.status_code != 200:
        return False, f'COREZ ответил ошибкой {ответ.status_code}: {ответ.text[:200]}'

    return True, 'Судья добавлен в судейскую коллегию COREZ.'
