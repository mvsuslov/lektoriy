from django import template

register = template.Library()


@register.filter
def ru_plural(n, forms):
    """Склонение: {{ n|ru_plural:"материал,материала,материалов" }}"""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return forms.split(",")[2]
    forms = forms.split(",")
    if n % 100 in range(11, 20):
        return forms[2]
    if n % 10 == 1:
        return forms[0]
    if n % 10 in (2, 3, 4):
        return forms[1]
    return forms[2]