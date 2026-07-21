from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import portal_login

urlpatterns = [
    # Своя страница входа — ВАЖНО: выше admin.site.urls,
    # чтобы перехватить /upr-m4x8k2/login/ раньше Джанги
    path("upr-m4x8k2/login/", portal_login, name="portal_login"),
    path("upr-m4x8k2/", admin.site.urls),
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)