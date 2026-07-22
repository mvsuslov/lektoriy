from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
import bleach
import re

from .models import Attachment, Link, Material, Subject

# ==== ДОБАВЛЕНО: список разрешённых видеохостингов ====
ALLOWED_VIDEO_HOSTS = {
    'youtube.com', 'www.youtube.com', 'youtu.be',
    'rutube.ru', 'www.rutube.ru',
    'vk.com', 'www.vk.com', 'video.vk.com',
    'yandex.ru', 'video.yandex.ru',  # если используете Яндекс.Видео
}

# ==== ДОБАВЛЕНО: разрешённые теги и атрибуты для embed_code через bleach ====
ALLOWED_EMBED_TAGS = ['iframe', 'div', 'span', 'p', 'br', 'strong', 'em', 'u', 'a']
ALLOWED_EMBED_ATTRIBUTES = {
    'iframe': ['src', 'width', 'height', 'allowfullscreen', 'loading', 'frameborder', 'allow'],
    'a': ['href', 'target', 'rel'],
    '*': ['class', 'style'],
}
# Дополнительно разрешаем только протоколы http, https (блокируем javascript: и data:)
ALLOWED_EMBED_PROTOCOLS = ['http', 'https']


class TeacherMaterialForm(forms.ModelForm):
    """Упрощённая форма публикации для преподавателя."""

    class Meta:
        model = Material
        fields = ("subject", "title", "type", "excerpt", "content",
                  "video_url", "embed_code")
        widgets = {
            "subject": forms.HiddenInput(),
            "type": forms.HiddenInput(),
            "title": forms.TextInput(attrs={
                "class": "f-input",
                "placeholder": "Например: Законы Ньютона — конспект урока",
            }),
            "excerpt": forms.Textarea(attrs={
                "class": "f-input", "rows": 3,
                "placeholder": "1–2 предложения: что внутри и для кого",
            }),
            "content": CKEditor5Widget(config_name="default"),
            "video_url": forms.URLInput(attrs={
                "class": "f-input",
                "placeholder": "https://… (YouTube, RuTube, VK Видео)",
            }),
            "embed_code": forms.Textarea(attrs={
                "class": "f-input", "rows": 3,
                "placeholder": "Код встраивания (iframe) для интерактивных моделей",
            }),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher:
            self.fields["subject"].queryset = teacher.subjects.all()
        self.fields["subject"].empty_label = None
        self.fields["content"].required = False
        self.fields["content"].label = "Текст материала"
        self.fields["video_url"].required = False
        self.fields["embed_code"].required = False

    # ==== ДОБАВЛЕНО: валидация video_url ====
    def clean_video_url(self):
        url = self.cleaned_data.get('video_url', '').strip()
        if not url:
            return url
        # Проверяем, что ссылка начинается с http:// или https://
        if not url.startswith(('http://', 'https://')):
            raise forms.ValidationError("Ссылка должна начинаться с http:// или https://")
        # Проверяем, что домен входит в разрешённый список
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        # Убираем www. для сравнения
        hostname = hostname.lower().replace('www.', '')
        allowed = False
        for allowed_host in ALLOWED_VIDEO_HOSTS:
            if allowed_host in hostname or hostname == allowed_host:
                allowed = True
                break
        if not allowed:
            raise forms.ValidationError(
                f"Разрешены только видео с {', '.join(ALLOWED_VIDEO_HOSTS)}."
            )
        return url

    # ==== ДОБАВЛЕНО: валидация и очистка embed_code ====
    def clean_embed_code(self):
        code = self.cleaned_data.get('embed_code', '').strip()
        if not code:
            return code

        try:
            import bleach
        except ImportError:
            # Если bleach не установлен, возвращаем код как есть (но лучше установить)
            return code

        # Разрешаем только iframe с безопасными атрибутами
        allowed_tags = ['iframe']
        allowed_attrs = {
            'iframe': ['src', 'width', 'height', 'allowfullscreen', 'loading', 'frameborder', 'allow'],
        }
        allowed_protocols = ['http', 'https']

        # Очищаем через bleach
        cleaned = bleach.clean(
            code,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=allowed_protocols,
            strip=True
        )

        # Дополнительная проверка: убедимся, что src начинается с http:// или https://
        # Просто удаляем iframe, если src небезопасен
        import re
        iframe_pattern = re.compile(r'<iframe\s+(.*?)>', re.IGNORECASE | re.DOTALL)

        def safe_iframe(match):
            attrs = match.group(1)
            src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if src_match:
                src = src_match.group(1)
                if not src.startswith(('http://', 'https://')):
                    return ''  # удаляем небезопасный iframe
            # Возвращаем iframe с теми же атрибутами
            return f'<iframe {attrs}>'

        cleaned = re.sub(iframe_pattern, safe_iframe, cleaned, flags=re.IGNORECASE | re.DOTALL)

        return cleaned


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ("file", "title")
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "f-input",
                "placeholder": "Название файла (необязательно)",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].required = False
        self.fields["title"].required = False


class LinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ("title", "url")
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "f-input",
                "placeholder": "Например: Задачи ВсОШ прошлых лет",
            }),
            "url": forms.URLInput(attrs={
                "class": "f-input",
                "placeholder": "https://…",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["url"].required = False

    def clean(self):
        cleaned = super().clean()
        title, url = cleaned.get("title"), cleaned.get("url")
        if url and not title:
            cleaned["title"] = url
        return cleaned