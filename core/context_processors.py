from .models import Direction


def portal_menu(request):
    """Направления с предметами для мега-меню — на каждой странице."""
    directions = Direction.objects.prefetch_related("subjects").all()
    return {"menu_directions": directions}