from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from django.core.exceptions import ValidationError

MAX_FILE_SIZE = 1.5 * 1024 * 1024  # 2 МБ — поменяете число, когда будет нужно


def validate_file_size(file):
    if file.size > MAX_FILE_SIZE:
        limit_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise ValidationError(
            f"Файл слишком большой. Максимум {limit_mb} МБ. "
            f"Большие файлы разместите на внешнем диске и добавьте ссылку."
        )


class Direction(models.Model):
    """Направление: «Точные науки», «Гуманитарные» и т.д. Создаёт только суперпользователь."""
    name = models.CharField("Название", max_length=100)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Направление"
        verbose_name_plural = "Направления"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

SUBJECT_EMOJIS = [
    ('', '— без эмодзи —'),
    # Школьные предметы
    ('📐', '📐 Математика'),
    ('➗', '➗ Алгебра'),
    ('📏', '📏 Геометрия'),
    ('⚛️', '⚛️ Физика'),
    ('🧪', '🧪 Химия'),
    ('🧬', '🧬 Биология'),
    ('🌍', '🌍 География'),
    ('📜', '📜 История'),
    ('🏛️', '🏛️ Обществознание'),
    ('📖', '📖 Литература'),
    ('✏️', '✏️ Русский язык'),
    ('🇬🇧', '🇬🇧 Английский язык'),
    ('🇩🇪', '🇩🇪 Немецкий язык'),
    ('🇫🇷', '🇫🇷 Французский язык'),
    ('🇨🇳', '🇨🇳 Китайский язык'),
    ('💻', '💻 Информатика'),
    ('🎨', '🎨 Искусство/ИЗО'),
    ('🎵', '🎵 Музыка'),
    ('⚽', '⚽ Физкультура'),
    ('🔭', '🔭 Астрономия'),
    ('🤖', '🤖 Робототехника'),
    ('🧮', '🧮 Олимпиадная математика'),
    # Языки программирования и технологии
    ('🐍', '🐍 Python'),
    ('☕', '☕ Java'),
    ('⚡', '⚡ C++'),
    ('🔷', '🔷 C#'),
    ('🌐', '🌐 JavaScript'),
    ('📜', '📜 TypeScript'),
    ('🐘', '🐘 PHP'),
    ('💎', '💎 Ruby'),
    ('🐹', '🐹 Go'),
    ('🦀', '🦀 Rust'),
    ('🍎', '🍎 Swift'),
    ('🤖', '🤖 Kotlin'),
    ('🎯', '🎯 Dart'),
    ('🗄️', '🗄️ SQL/Базы данных'),
    ('🖥️', '🖥️ Веб-разработка (HTML/CSS)'),
    ('📊', '📊 Анализ данных'),
    ('🧠', '🧠 Machine Learning'),
    ('🐧', '🐧 Linux/Администрирование'),
    ('🎮', '🎮 Разработка игр'),
]

class Subject(models.Model):
    """Предмет. Привязан к направлению, может быть скрытым."""
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Адрес (slug)", unique=True)
    direction = models.ForeignKey(
        Direction, on_delete=models.PROTECT,
        related_name="subjects", verbose_name="Направление"
    )
    emoji = models.CharField(
        'Эмодзи',
        max_length=8,
        choices=SUBJECT_EMOJIS,
        blank=True,
        default='',
        help_text='Иконка предмета для меню и страниц'
    )
    icon = models.CharField("Иконка (эмодзи)", max_length=10, default="📚")
    color = models.CharField("Цвет (hex)", max_length=7, default="#2563EB")
    description = models.CharField("Короткое описание", max_length=250, blank=True)
    is_hidden = models.BooleanField(
        "Скрытый предмет", default=False,
        help_text="Не показывается на главной, в меню и поиске. "
                  "Доступен только по прямой ссылке. Для частных занятий."
    )
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class TeacherProfile(models.Model):
    """Профиль преподавателя. Один-к-одному с пользователем."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="teacher_profile", verbose_name="Пользователь"
    )
    first_name = models.CharField("Имя", max_length=50)
    middle_name = models.CharField("Отчество", max_length=50)
    last_name = models.CharField("Фамилия", max_length=50)
    show_last_name = models.BooleanField(
        "Показывать фамилию на сайте", default=True,
        help_text="Если выключено, на сайте будет «Имя Отчество Ф.»"
    )
    code = models.SlugField(
        "Код страницы", unique=True,
        help_text="Латиница, коротко. Адрес: /t/код/"
    )
    role = models.CharField(
        "Должность", max_length=150, blank=True,
        help_text="Например: учитель физики и информатики"
    )
    bio = models.TextField("О себе", blank=True)
    color = models.CharField("Цвет аватара (hex)", max_length=7, default="#4F46E5")
    brand_symbol = models.CharField(
        "Символ логотипа кабинета", max_length=10, blank=True,
        help_text="Например: ∑. Если пусто — будут инициалы"
    )
    brand_title = models.CharField(
        "Название кабинета", max_length=100, blank=True,
        help_text="Например: Физика и код. Если пусто — отображаемое имя"
    )
    subjects = models.ManyToManyField(
        Subject, related_name="teachers", verbose_name="Предметы", blank=True
    )

    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}"

    def display_name(self):
        """Полное отображаемое имя (с учётом переключателя)."""
        if self.show_last_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.middle_name} {self.last_name[0]}."

    def short_name(self):
        """Компактный формат для карточек и фильтров."""
        return f"{self.first_name} {self.middle_name} {self.last_name[0]}."

    def initials(self):
        return f"{self.first_name[0]}{self.middle_name[0]}"


def attachment_path(instance, filename):
    return f"materials/{instance.material_id}/{filename}"


class Material(models.Model):
    class Type(models.TextChoices):
        LESSON = "lesson", "Конспект"
        PRACTICE = "practice", "Разработка"
        VIDEO = "video", "Видео"
        INTERACTIVE = "interactive", "Интерактив"
        ARTICLE = "article", "Статья"

    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT,
        related_name="materials", verbose_name="Предмет"
    )
    author = models.ForeignKey(
        TeacherProfile, on_delete=models.PROTECT,
        related_name="materials", verbose_name="Автор",
        help_text="Заполняется автоматически"
    )
    title = models.CharField("Заголовок", max_length=200)
    slug = models.SlugField("Адрес (slug)", unique=True, max_length=220)
    type = models.CharField(
        "Тип", max_length=20, choices=Type.choices, default=Type.LESSON
    )
    excerpt = models.CharField(
        "Краткое описание", max_length=300,
        help_text="Показывается в карточке материала"
    )
    content = CKEditor5Field("Содержание", config_name="default", blank=True)
    video_url = models.URLField(
        "Ссылка на видео", blank=True,
        help_text="YouTube, RuTube или VK Видео — будет встроен плеер"
    )
    embed_code = models.TextField(
        "Код встраивания (интерактив)", blank=True,
        help_text="iframe PhET, GeoGebra и т.п. Только для типа «Интерактив»"
    )
    is_published = models.BooleanField("Опубликовано", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Материал"
        verbose_name_plural = "Материалы"
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=False) or "material"
            slug, i = base[:210], 2
            while Material.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base[:205]}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Attachment(models.Model):
    """Файл, прикреплённый к материалу."""
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        related_name="attachments", verbose_name="Материал"
    )
    file = models.FileField("Файл", upload_to=attachment_path, validators=[validate_file_size])
    title = models.CharField("Название для отображения", max_length=200, blank=True)

    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"

    def __str__(self):
        return self.title or self.file.name.split("/")[-1]

    def filename(self):
        return self.file.name.split("/")[-1]


class Link(models.Model):
    """Полезная ссылка, прикреплённая к материалу."""
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        related_name="links", verbose_name="Материал"
    )
    title = models.CharField("Название", max_length=200)
    url = models.URLField("Адрес")

    class Meta:
        verbose_name = "Ссылка"
        verbose_name_plural = "Ссылки"

    def __str__(self):
        return self.title
