from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import portal_login

urlpatterns = [
    # Своя страница входа — выше admin.site.urls
    path("upr-m4x8k2/login/", portal_login, name="portal_login"),
    path("upr-m4x8k2/", admin.site.urls),

    # CKEditor 5 (новый)
    path("ckeditor5/", include("django_ckeditor_5.urls")),

    # Старый CKEditor для админки (загрузка картинок)
    path('ckeditor/', include('ckeditor_uploader.urls')),

    # Основные URL — ВАЖНО: после специфических префиксов!
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)