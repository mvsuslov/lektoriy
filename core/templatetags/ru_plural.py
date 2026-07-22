from django import template

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


# ==== НОВЫЙ ФИЛЬТР: преобразование секунд в человеко-читаемый формат ====
@register.filter
def seconds_to_human(seconds):
    """
    Преобразует количество секунд в строку вида "3 часа", "1 час", "45 минут" и т.д.
    """
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return "неизвестно"

    if seconds < 0:
        return "0 секунд"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        # Склоняем "час"
        if hours == 1:
            hour_word = "час"
        elif 2 <= hours <= 4:
            hour_word = "часа"
        else:
            hour_word = "часов"
        if minutes > 0:
            # Склоняем "минута"
            if minutes == 1:
                min_word = "минута"
            elif 2 <= minutes <= 4:
                min_word = "минуты"
            else:
                min_word = "минут"
            return f"{hours} {hour_word} {minutes} {min_word}"
        else:
            return f"{hours} {hour_word}"
    elif minutes > 0:
        if minutes == 1:
            min_word = "минута"
        elif 2 <= minutes <= 4:
            min_word = "минуты"
        else:
            min_word = "минут"
        return f"{minutes} {min_word}"
    else:
        return f"{secs} секунд"