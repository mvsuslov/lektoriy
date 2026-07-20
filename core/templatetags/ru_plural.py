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