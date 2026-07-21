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