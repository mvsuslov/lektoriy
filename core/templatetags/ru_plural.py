from django import template
from datetime import timedelta

register = template.Library()


@register.filter
def ru_plural(value, forms):
    """
    Склонение русских слов по числу.
    forms: строка вида "материал,материала,материалов"
    """
    try:
        value = int(value)
    except (ValueError, TypeError):
        return forms.split(',')[0]

    forms_list = forms.split(',')
    if len(forms_list) != 3:
        return forms_list[0]

    if value % 10 == 1 and value % 100 != 11:
        return forms_list[0]  # 1, 21, 31... (но не 11)
    elif 2 <= value % 10 <= 4 and (value % 100 < 10 or value % 100 >= 20):
        return forms_list[1]  # 2-4, 22-24... (но не 12-14)
    else:
        return forms_list[2]  # 0, 5-20, 25-30...


@register.filter
def seconds_to_human(value):
    """
    Преобразует секунды или timedelta в человекочитаемый формат.
    """
    # Если это timedelta, извлекаем секунды
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
    else:
        try:
            seconds = int(value)
        except (ValueError, TypeError):
            return "неизвестное время"

    if seconds <= 0:
        return "0 секунд"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []

    if hours > 0:
        if hours == 1:
            parts.append(f"{hours} час")
        elif 2 <= hours <= 4:
            parts.append(f"{hours} часа")
        else:
            parts.append(f"{hours} часов")

    if minutes > 0:
        if minutes == 1:
            parts.append(f"{minutes} минуту")
        elif 2 <= minutes <= 4:
            parts.append(f"{minutes} минуты")
        else:
            parts.append(f"{minutes} минут")

    # Секунды показываем только если нет часов/минут
    if not parts and secs > 0:
        if secs == 1:
            parts.append(f"{secs} секунду")
        elif 2 <= secs <= 4:
            parts.append(f"{secs} секунды")
        else:
            parts.append(f"{secs} секунд")

    return " ".join(parts) if parts else "0 секунд"