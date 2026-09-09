from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from django.conf import settings as dj_settings
import bleach
import re

from .models import Attachment, Link, Material, Review, Subject

# ==== ДОБАВЛЕНО: список разрешённых видеохостингов ====
ALLOWED_VIDEO_HOSTS = {
    'youtube.com', 'www.youtube.com', 'youtu.be',
    'rutube.ru', 'www.rutube.ru',
    'vk.com', 'www.vk.com', 'video.vk.com',
    'yandex.ru', 'video.yandex.ru',
}

# ==== ДОБАВЛЕНО: разрешённые теги и атрибуты для embed_code через bleach ====
ALLOWED_EMBED_TAGS = ['iframe', 'div', 'span', 'p', 'br', 'strong', 'em', 'u', 'a']
ALLOWED_EMBED_ATTRIBUTES = {
    'iframe': ['src', 'width', 'height', 'allowfullscreen', 'loading', 'frameborder', 'allow'],
    'a': ['href', 'target', 'rel'],
    '*': ['class', 'style'],
}
ALLOWED_EMBED_PROTOCOLS = ['http', 'https']


class TeacherMaterialForm(forms.ModelForm):
    """Упрощённая форма публикации для преподавателя."""

    class Meta:
        model = Material
        fields = ("subject", "title", "type", "excerpt", "content",
                  "content_format", "content_md",
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
            "content_md": forms.HiddenInput(),  # заполняется из iframe редактора
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
        self.fields["content_md"].required = False
        self.fields["video_url"].required = False
        self.fields["embed_code"].required = False

    def clean(self):
        cleaned = super().clean()
        fmt = cleaned.get("content_format", "html")
        if fmt == "md" and not cleaned.get("content_md", "").strip():
            self.add_error("content_format",
                           "Введите текст в Markdown-редакторе и нажмите «Перенести в материал»")
        return cleaned

    def clean_video_url(self):
        url = self.cleaned_data.get('video_url', '').strip()
        if not url:
            return url
        if not url.startswith(('http://', 'https://')):
            raise forms.ValidationError("Ссылка должна начинаться с http:// или https://")
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
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

    def clean_embed_code(self):
        code = self.cleaned_data.get('embed_code', '').strip()
        if not code:
            return code

        # Очистка через bleach
        cleaned = bleach.clean(
            code,
            tags=['iframe'],
            attributes=ALLOWED_EMBED_ATTRIBUTES,
            protocols=ALLOWED_EMBED_PROTOCOLS,
            strip=True
        )

        # Дополнительная проверка src
        iframe_pattern = re.compile(r'<iframe\s+(.*?)>', re.IGNORECASE | re.DOTALL)

        def safe_iframe(match):
            attrs = match.group(1)
            src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if src_match:
                src = src_match.group(1)
                if not src.startswith(('http://', 'https://')):
                    return ''
            return f'<iframe {attrs}>'

        cleaned = re.sub(iframe_pattern, safe_iframe, cleaned)
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


class ReviewForm(forms.Form):
    title = forms.CharField(
        label="Название проверки", max_length=200,
        widget=forms.TextInput(attrs={
            "class": "f-input",
            "placeholder": "Например: Конспект «Закон Ома», 8 класс",
        })
    )
    level = forms.ChoiceField(
        label="Уровень образования",
        choices=Review.Level.choices,
        widget=forms.RadioSelect  # стилизуем чипсами в шаблоне
    )
    input_text = forms.CharField(
        label="Текст конспекта или методической разработки",
        widget=forms.Textarea(attrs={
            "class": "f-input", "rows": 14,
            "placeholder": "Вставьте текст сюда…",
        })
    )

    def clean_input_text(self):
        text = self.cleaned_data["input_text"].strip()
        if len(text) < 300:
            raise forms.ValidationError(
                "Текст слишком короткий (минимум 300 символов) — "
                "анализ будет бессмысленным."
            )
        if len(text) > dj_settings.REVIEW_MAX_CHARS:
            raise forms.ValidationError(
                f"Текст слишком длинный. Максимум "
                f"{dj_settings.REVIEW_MAX_CHARS} символов."
            )
        return text

import random

class TeacherRegisterForm(forms.Form):
    email = forms.EmailField(
        label="Email (будет логином)",
        widget=forms.EmailInput(attrs={"class": "f-input", "placeholder": "you@example.com"})
    )
    password1 = forms.CharField(
        label="Пароль", min_length=8,
        widget=forms.PasswordInput(attrs={"class": "f-input", "placeholder": "Минимум 8 символов"})
    )
    password2 = forms.CharField(
        label="Пароль ещё раз",
        widget=forms.PasswordInput(attrs={"class": "f-input"})
    )
    last_name = forms.CharField(
        label="Фамилия", max_length=50,
        widget=forms.TextInput(attrs={"class": "f-input", "placeholder": "Иванов"})
    )
    first_name = forms.CharField(
        label="Имя", max_length=50,
        widget=forms.TextInput(attrs={"class": "f-input", "placeholder": "Иван"})
    )
    middle_name = forms.CharField(
        label="Отчество", max_length=50,
        widget=forms.TextInput(attrs={"class": "f-input", "placeholder": "Иванович"})
    )
    role = forms.CharField(
        label="Должность", max_length=150, required=False,
        widget=forms.TextInput(attrs={
            "class": "f-input", "placeholder": "Например: учитель физики, МБОУ СОШ №5"
        })
    )
    subjects = forms.ModelMultipleChoiceField(
        label="Предметы, которые будете вести",
        queryset=Subject.objects.filter(is_hidden=False),
        widget=forms.CheckboxSelectMultiple
    )
    subject_tagline = forms.CharField(
        label="Слоган к предмету", max_length=250, required=False,
        widget=forms.TextInput(attrs={
            "class": "f-input", "placeholder": "Например: Физика — просто и с интересом"
        })
    )
    about = forms.CharField(
        label="Пара слов о себе", required=False,
        widget=forms.Textarea(attrs={
            "class": "f-input", "rows": 3,
            "placeholder": "Где работаете, стаж, что планируете публиковать…"
        })
    )
    # Антибот
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    captcha = forms.IntegerField(label="Антибот-вопрос")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._a, self._b = random.randint(2, 9), random.randint(2, 9)
        if self.data:
            try:
                self._a = int(self.data.get("_a", 0))
                self._b = int(self.data.get("_b", 0))
            except (TypeError, ValueError):
                pass
        self.fields["captcha"].label = f"Сколько будет {self._a} + {self._b}?"
        self.fields["captcha"].widget.attrs.update({
            "class": "f-input", "placeholder": "Ответ цифрой", "autocomplete": "off"
        })

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Аккаунт с таким email уже существует.")
        from .models import TeacherApplication
        if TeacherApplication.objects.filter(email=email, status="pending").exists():
            raise forms.ValidationError("Заявка с этим email уже подана и ожидает рассмотрения.")
        return email

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Спам.")
        return ""

    def clean_captcha(self):
        val = self.cleaned_data.get("captcha")
        try:
            a = int(self.data.get("_a", -1))
            b = int(self.data.get("_b", -1))
        except (TypeError, ValueError):
            raise forms.ValidationError("Ошибка проверки. Попробуйте ещё раз.")
        if val != a + b:
            raise forms.ValidationError("Неверный ответ. Попробуйте ещё раз.")
        return val

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Пароли не совпадают.")
        return cleaned