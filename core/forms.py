from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Attachment, Link, Material, Subject


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
            "content": CKEditor5Widget(config_name="default"),   # ← было Textarea
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
        # Убираем пустой вариант «---------» из предметов
        self.fields["subject"].empty_label = None
        # Необязательные поля
        self.fields["content"].required = False
        self.fields["content"].label = "Текст материала"
        self.fields["video_url"].required = False
        self.fields["embed_code"].required = False


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
        """Ссылка сохраняется, только если заполнены оба поля."""
        cleaned = super().clean()
        title, url = cleaned.get("title"), cleaned.get("url")
        if url and not title:
            cleaned["title"] = url  # если название забыли — подставим адрес
        return cleaned