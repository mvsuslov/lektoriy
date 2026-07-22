from datetime import timedelta

from django.conf import settings
from django.db.models import Count

from .models import Direction


def portal_menu(request):
    """Направления с предметами для мега-меню и плиток — на каждой странице.

    К каждому предмету добавляется .pub_count — количество
    ОПУБЛИКОВАННЫХ материалов (скрытые не считаются).
    """
    directions = Direction.objects.prefetch_related("subjects").all()
    for d in directions:
        counts = dict(
            d.subjects.filter(materials__is_published=True)
            .annotate(c=Count("materials"))
            .values_list("id", "c")
        )
        for s in d.subjects.all():
            s.pub_count = counts.get(s.id, 0)
    return {"menu_directions": directions}


def axes_cooloff(request):
    """
    Передаёт время блокировки axes (в секундах) во все шаблоны.

    Нужен, потому что django-axes сам не передаёт cooloff_time
    в шаблон блокировки. AXES_COOLOFF_TIME задаётся в ЧАСАХ —
    переводим в секунды для фильтра seconds_to_human.
    """
    cooloff = getattr(settings, 'AXES_COOLOFF_TIME', 3)
    if isinstance(cooloff, timedelta):
        seconds = int(cooloff.total_seconds())
    else:
        seconds = int(float(cooloff) * 3600)  # часы → секунды
    return {'axes_cooloff_seconds': seconds}