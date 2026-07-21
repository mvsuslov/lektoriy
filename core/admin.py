from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import (Attachment, Direction, Link, Material, Subject,
                     TeacherProfile)

User = get_user_model()


def is_super(user):
    return user.is_superuser


# ============ Направления — только суперпользователь ============
@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)

    def has_view_permission(self, request, obj=None):
        return is_super(request.user)

    def has_add_permission(self, request):
        return is_super(request.user)

    def has_change_permission(self, request, obj=None):
        return is_super(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_super(request.user)

    def has_module_permission(self, request):
        return is_super(request.user)


# ============ Предметы — создаёт и скрывает только суперпользователь ============
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "direction", "is_hidden", "order")
    list_filter = ("direction", "is_hidden")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}

    def get_readonly_fields(self, request, obj=None):
        # Скрытие предмета — только суперпользователь
        if not is_super(request.user):
            return ("is_hidden",)
        return ()

    def has_add_permission(self, request):
        return is_super(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_super(request.user)


# ============ Вложения и ссылки — прямо в карточке материала ============
class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 1


class LinkInline(admin.TabularInline):
    model = Link
    extra = 1


# ============ Материалы — преподаватель видит только свои ============
@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "type", "author_name", "is_published", "created_at")
    list_filter = ("subject", "type", "is_published")
    search_fields = ("title", "excerpt")
    inlines = [AttachmentInline, LinkInline]
    readonly_fields = ("author",)
    exclude = ("slug",)

    @admin.display(description="Автор")
    def author_name(self, obj):
        return str(obj.author)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_super(request.user):
            return qs
        profile = getattr(request.user, "teacher_profile", None)
        if profile:
            return qs.filter(author=profile)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # В списке предметов — только назначенные преподавателю
        if db_field.name == "subject" and not is_super(request.user):
            profile = getattr(request.user, "teacher_profile", None)
            if profile:
                kwargs["queryset"] = profile.subjects.all()
            else:
                kwargs["queryset"] = Subject.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Автор подставляется автоматически
        if not obj.author_id:
            profile = getattr(request.user, "teacher_profile", None)
            if profile:
                obj.author = profile
            else:
                # суперпользователь без профиля — берём первый профиль
                # (или создайте себе TeacherProfile, см. инструкцию)
                obj.author = TeacherProfile.objects.first()
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if is_super(request.user):
            return True
        profile = getattr(request.user, "teacher_profile", None)
        if obj is None:
            return profile is not None
        return profile and obj.author_id == profile.id

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


# ============ Преподаватели ============
@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("__str__", "code", "role", "show_last_name", "subjects_list")
    filter_horizontal = ("subjects",)
    fieldsets = (
        ("Личные данные", {
            "fields": ("user", "first_name", "middle_name", "last_name", "show_last_name")
        }),
        ("Страница кабинета", {
            "fields": ("code", "role", "color", "brand_symbol", "brand_title",
                       "brand_headline", "brand_tagline", "subjects")
        }),
    )

    @admin.display(description="Предметы")
    def subjects_list(self, obj):
        return ", ".join(s.name for s in obj.subjects.all())

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_super(request.user):
            return qs
        # Преподаватель видит только свой профиль
        return qs.filter(user=request.user)

    def get_readonly_fields(self, request, obj=None):
        if not is_super(request.user):
            # Преподаватель не может менять код, предметы и привязку к пользователю
            return ("user", "code", "subjects")
        return ()

    def has_add_permission(self, request):
        # Новых преподавателей создаёт только суперпользователь
        return is_super(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_super(request.user)