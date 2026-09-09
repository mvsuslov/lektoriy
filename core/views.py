from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import logout as auth_logout
from django.views.decorators.http import require_POST
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from django.core.cache import cache

from axes.decorators import axes_dispatch

from .forms import AttachmentForm, LinkForm, TeacherMaterialForm
from .models import Material, Subject, TeacherProfile

import hashlib
import threading

from django.http import JsonResponse
from django.utils import timezone

from .forms import ReviewForm
from .models import Review, SiteSettings
from .review_service import make_hash, run_analysis
from .md_render import render_md

from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from .forms import TeacherRegisterForm
from .models import TeacherApplication
import secrets

PER_PAGE = 6


def teacher_required(view_func):
    """Кабинет невидим снаружи: незалогиненным — 404, а не страница входа."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper


def public_materials():
    """Опубликованные материалы не из скрытых предметов."""
    return Material.objects.filter(
        is_published=True, subject__is_hidden=False
    ).select_related("subject", "author")


def portal_home(request):
    recent = public_materials().order_by("-created_at")[:6]
    teachers = (
        TeacherProfile.objects
        .annotate(
            pub_count=Count(
                "materials",
                filter=Q(materials__is_published=True,
                         materials__subject__is_hidden=False),
            )
        )
        .order_by("-pub_count")[:6]
    )
    return render(request, "portal/home.html", {
        "recent": recent,
        "teachers": teachers,
        "teachers_total": TeacherProfile.objects.count(),
    })


def all_subjects(request):
    subjects = Subject.objects.filter(is_hidden=False).select_related('direction')
    return render(request, "portal/subjects.html", {"subjects": subjects})


def subject_detail(request, slug):
    subject = get_object_or_404(Subject, slug=slug)

    materials = Material.objects.filter(
        subject=subject, is_published=True
    ).select_related("author", "subject")

    teacher_code = request.GET.get("teacher", "")
    type_filter = request.GET.get("type", "")
    if teacher_code:
        materials = materials.filter(author__code=teacher_code)
    if type_filter:
        materials = materials.filter(type=type_filter)

    paginator = Paginator(materials, PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "portal/subject.html", {
        "subject": subject,
        "page": page,
        "teachers": subject.teachers.all(),
        "types": materials.values_list("type", flat=True).distinct() if not type_filter
                 else Material.objects.filter(subject=subject, is_published=True)
                      .values_list("type", flat=True).distinct(),
        "current_teacher": teacher_code,
        "current_type": type_filter,
        "type_choices": Material.Type.choices,
    })


def material_detail(request, slug, material_slug):
    material = get_object_or_404(
        Material.objects.select_related("subject", "author")
                        .prefetch_related("attachments", "links"),
        subject__slug=slug, slug=material_slug, is_published=True,
    )

    rendered_md = None
    if material.content_format == "md" and material.content_md:
        cache_key = f"md_{material.pk}_{int(material.updated_at.timestamp())}"
        rendered_md = cache.get(cache_key)
        if rendered_md is None:
            rendered_md = render_md(material.content_md)
            cache.set(cache_key, rendered_md, 60 * 60 * 24 * 7)  # 7 дней

    return render(request, "portal/material.html", {
        "material": material,
        "rendered_md": rendered_md,
    })

def teachers_list(request):
    query = request.GET.get("q", "").strip()
    letter = request.GET.get("letter", "").strip()

    teachers = TeacherProfile.objects.all().order_by("last_name", "first_name")
    if query:
        teachers = teachers.filter(
            Q(first_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    if letter:
        ranges_map = {
            "А": "АБВ", "Г": "ГДЕЁЖ", "З": "ЗИК", "Л": "ЛМН",
            "О": "ОПР", "С": "СТУ", "Ф": "ФХЦЧ", "Ш": "ШЩЭЮЯ",
        }
        letters = ranges_map.get(letter, letter)
        q_filter = Q()
        for ch in letters:
            q_filter |= Q(last_name__istartswith=ch)
        teachers = teachers.filter(q_filter)

    ranges = [("А", "В"), ("Г", "Ж"), ("З", "К"), ("Л", "Н"),
              ("О", "Р"), ("С", "У"), ("Ф", "Ч"), ("Ш", "Я")]
    letters_in_use = set(
        TeacherProfile.objects.values_list("last_name", flat=True)
    )
    active_ranges = []
    for start, end in ranges:
        if any(start <= n[0].upper() <= end for n in letters_in_use if n):
            active_ranges.append((start, end))

    return render(request, "portal/teachers.html", {
        "teachers": teachers,
        "active_ranges": active_ranges,
        "query": query,
        "letter": letter,
        "teachers_total": TeacherProfile.objects.count(),
    })


def teacher_home(request, code):
    teacher = get_object_or_404(
        TeacherProfile.objects.prefetch_related("subjects"), code=code
    )
    base = teacher.materials.filter(
        is_published=True, subject__is_hidden=False
    ).select_related("subject")

    public_subjects = list(teacher.subjects.filter(is_hidden=False))
    counts = dict(
        base.values_list("subject_id")
            .annotate(c=Count("id"))
            .values_list("subject_id", "c")
    )
    for s in public_subjects:
        s.pub_count = counts.get(s.id, 0)

    view_mode = request.GET.get("view", "recent")
    return render(request, "teacher/home.html", {
        "teacher": teacher,
        "recent": base.order_by("-created_at")[:6],
        "materials": base.order_by("created_at"),
        "public_subjects": public_subjects,
        "view_mode": view_mode,
    })


def teacher_subject(request, code, subject_slug):
    teacher = get_object_or_404(TeacherProfile, code=code)
    subject = get_object_or_404(Subject, slug=subject_slug)

    if not teacher.subjects.filter(pk=subject.pk).exists():
        return render(request, "404.html", status=404)

    if subject.is_hidden:
        user = request.user
        if not (user.is_superuser or (
            hasattr(user, 'teacher_profile') and
            user.teacher_profile.subjects.filter(pk=subject.pk).exists()
        )):
            raise Http404("Предмет скрыт")

    materials = Material.objects.filter(
        author=teacher, subject=subject, is_published=True
    ).select_related("subject")

    type_filter = request.GET.get("type", "")
    if type_filter:
        materials = materials.filter(type=type_filter)

    paginator = Paginator(materials, PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "teacher/subject.html", {
        "teacher": teacher,
        "subject": subject,
        "page": page,
        "types": Material.objects.filter(
            author=teacher, subject=subject, is_published=True
        ).values_list("type", flat=True).distinct(),
        "current_type": type_filter,
        "type_choices": Material.Type.choices,
    })


def search(request):
    query = request.GET.get("q", "").strip()
    results = public_materials().none()
    if query:
        results = public_materials().filter(
            Q(title__icontains=query) | Q(excerpt__icontains=query)
        )
    return render(request, "portal/search.html", {
        "query": query, "results": results,
    })


# ------------------------------------------------------------------
# Вход на портал
# ------------------------------------------------------------------

@axes_dispatch
def portal_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect("admin:index")
        return redirect("desk_home")

    error = ""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect(request.GET.get("next") or "admin:index")
            return redirect("desk_home")
        error = "Неверная почта или пароль. Попробуйте ещё раз."

    return render(request, "desk/login.html", {"error": error})

# ------------------------------------------------------------------
# Кабинет преподавателя
# ------------------------------------------------------------------

def get_teacher(request):
    return getattr(request.user, "teacher_profile", None)


@teacher_required
def desk_home(request):
    teacher = get_teacher(request)
    if not teacher:
        messages.error(request, "У вашей учётной записи нет профиля преподавателя. "
                                "Обратитесь к администратору портала.")
        return redirect("portal_home")
    materials = teacher.materials.select_related("subject")
    form = TeacherMaterialForm(teacher=teacher)
    return render(request, "desk/home.html", {
        "teacher": teacher,
        "materials": materials,
        "form": form,
        "review_enabled": SiteSettings.get().review_enabled,
    })


@teacher_required
def desk_material_new(request):
    teacher = get_teacher(request)
    if not teacher:
        return redirect("portal_home")

    if request.method == "POST":
        form = TeacherMaterialForm(request.POST, teacher=teacher)
        file_form = AttachmentForm(request.POST, request.FILES, prefix="file")
        link_form = LinkForm(request.POST, prefix="link")
        if form.is_valid() and file_form.is_valid() and link_form.is_valid():
            material = form.save(commit=False)
            material.author = teacher
            material.save()
            if file_form.cleaned_data.get("file"):
                attachment = file_form.save(commit=False)
                attachment.material = material
                attachment.save()
            if link_form.cleaned_data.get("url") and link_form.cleaned_data.get("title"):
                link = link_form.save(commit=False)
                link.material = material
                link.save()
            messages.success(request, "Материал опубликован! "
                                      "Ссылку можно отправлять ученикам.")
            return redirect("desk_home")
    else:
        form = TeacherMaterialForm(teacher=teacher)
        file_form = AttachmentForm(prefix="file")
        link_form = LinkForm(prefix="link")

    return render(request, "desk/new.html", {
        "teacher": teacher,
        "form": form,
        "file_form": file_form,
        "link_form": link_form,
    })


@teacher_required
def desk_material_edit(request, pk):
    teacher = get_teacher(request)
    material = get_object_or_404(Material, pk=pk)
    if not request.user.is_superuser and (not teacher or material.author != teacher):
        return redirect("desk_home")

    if request.method == "POST":
        form = TeacherMaterialForm(request.POST, instance=material,
                                   teacher=material.author)
        if form.is_valid():
            form.save()
            messages.success(request, "Изменения сохранены!")
            return redirect("desk_home")
    else:
        form = TeacherMaterialForm(instance=material, teacher=material.author)

    return render(request, "desk/new.html", {
        "teacher": teacher or material.author,
        "form": form,
        "file_form": AttachmentForm(prefix="file"),
        "link_form": LinkForm(prefix="link"),
        "editing": material,
    })


@teacher_required
def desk_material_toggle(request, pk):
    teacher = get_teacher(request)
    material = get_object_or_404(Material, pk=pk)
    if not request.user.is_superuser and material.author != teacher:
        return redirect("desk_home")
    material.is_published = not material.is_published
    material.save(update_fields=["is_published"])
    return redirect("desk_home")


@teacher_required
def desk_password(request):
    teacher = get_teacher(request)
    if not teacher:
        return redirect("portal_home")

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Пароль изменён! "
                                      "Используйте новый при следующем входе.")
            return redirect("desk_home")
    else:
        form = PasswordChangeForm(request.user)

    material_form = TeacherMaterialForm(teacher=teacher)
    return render(request, "desk/password.html", {
        "teacher": teacher,
        "form": material_form,
        "password_form": form,
    })


@require_POST
def desk_logout(request):
    auth_logout(request)
    return redirect("portal_home")


# ------------------------------------------------------------------
# Markdown-редактор
# ------------------------------------------------------------------

@teacher_required
@xframe_options_exempt
def desk_md_editor(request):
    """Страница с MD-редактором (для iframe)."""
    return render(request, "desk/md_editor.html")


@teacher_required
@require_POST
def desk_md_image_upload(request):
    """Загрузка картинки из md-редактора. Возвращает URL."""
    file = request.FILES.get("image")
    if not file:
        return JsonResponse({"error": "Файл не получен"}, status=400)

    allowed = {"image/png", "image/jpeg", "image/gif", "image/webp"}
    import magic as _magic
    file.seek(0)
    mime = _magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    if mime not in allowed:
        return JsonResponse({"error": "Только PNG/JPEG/GIF/WebP"}, status=400)
    if file.size > 1.5 * 1024 * 1024:
        return JsonResponse({"error": "Максимум 1.5 МБ"}, status=400)

    from django.core.files.storage import default_storage
    import os
    # уникальное имя, чтобы не перезаписывать
    name, ext = os.path.splitext(file.name)
    path = default_storage.save(f"md_images/{name}_{hashlib.md5(file.read()).hexdigest()[:8]}{ext}", file)
    return JsonResponse({"url": f"/media/{path}"})


# ------------------------------------------------------------------
# Методический анализ (DeepSeek)
# ------------------------------------------------------------------

def review_enabled_or_404():
    if not SiteSettings.get().review_enabled:
        raise Http404


def _run_review_in_thread(review_id):
    """Фоновый поток: вызывает API и записывает результат."""
    from django import db
    db.close_old_connections()
    try:
        review = Review.objects.get(pk=review_id)
        result = run_analysis(review.level, review.input_text)
        review.score = result.pop("score")
        review.result = result
        review.status = Review.Status.DONE
    except Exception as e:
        review.status = Review.Status.ERROR
        review.error = str(e)[:300]
    finally:
        review.save(update_fields=["score", "result", "status", "error"])
        db.close_old_connections()


@teacher_required
def desk_review_new(request):
    review_enabled_or_404()
    teacher = get_teacher(request)
    if not teacher:
        return redirect("portal_home")

    # Дневной лимит (ошибки не тратят лимит)
    today_count = Review.objects.filter(
        teacher=teacher,
        created_at__date=timezone.localdate(),
        from_cache=False,
    ).exclude(status=Review.Status.ERROR).count()

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            if today_count >= settings.REVIEW_DAILY_LIMIT:
                messages.error(request, "Дневной лимит исчерпан. "
                                        "Попробуйте завтра!")
                return redirect("desk_review_new")

            text = form.cleaned_data["input_text"]
            text_hash = make_hash(text)

            # Кэш: такой же текст уже проверялся этим преподавателем
            cached = Review.objects.filter(
                teacher=teacher, text_hash=text_hash,
                status=Review.Status.DONE,
            ).first()
            if cached:
                review = Review.objects.create(
                    teacher=teacher,
                    title=form.cleaned_data["title"],
                    level=form.cleaned_data["level"],
                    input_text=text, text_hash=text_hash,
                    status=Review.Status.DONE,
                    score=cached.score, result=cached.result,
                    from_cache=True,
                )
                messages.success(request, "Этот текст уже проверялся — "
                                          "показан сохранённый результат (бесплатно).")
                return redirect("desk_review_detail", pk=review.pk)

            review = Review.objects.create(
                teacher=teacher,
                title=form.cleaned_data["title"],
                level=form.cleaned_data["level"],
                input_text=text, text_hash=text_hash,
            )
            threading.Thread(
                target=_run_review_in_thread, args=(review.pk,), daemon=True
            ).start()
            return redirect("desk_review_detail", pk=review.pk)
    else:
        form = ReviewForm()

    return render(request, "desk/review_new.html", {
        "teacher": teacher,
        "form": form,
        "today_count": today_count,
        "daily_limit": settings.REVIEW_DAILY_LIMIT,
    })


@teacher_required
def desk_review_detail(request, pk):
    review_enabled_or_404()
    teacher = get_teacher(request)
    review = get_object_or_404(Review, pk=pk)
    if not request.user.is_superuser and review.teacher != teacher:
        raise Http404
    return render(request, "desk/review_detail.html", {
        "teacher": teacher, "review": review,
    })


@teacher_required
def desk_review_status(request, pk):
    """JSON-эндпоинт для поллинга со страницы результата."""
    review = get_object_or_404(Review, pk=pk)
    teacher = get_teacher(request)
    if not request.user.is_superuser and review.teacher != teacher:
        raise Http404
    return JsonResponse({
        "status": review.status,
        "score": review.score,
        "result": review.result,
        "error": review.error,
    })


@teacher_required
def desk_review_list(request):
    review_enabled_or_404()
    teacher = get_teacher(request)
    reviews = teacher.reviews.all() if teacher else Review.objects.none()
    return render(request, "desk/review_list.html", {
        "teacher": teacher, "reviews": reviews,
    })

# ------------------------------------------------------------------
# Регистрация преподавателей
# ------------------------------------------------------------------

def portal_register(request):
    if request.user.is_authenticated:
        return redirect("desk_home")

    if request.method == "POST":
        form = TeacherRegisterForm(request.POST)
        if form.is_valid():
            User = get_user_model()
            email = form.cleaned_data["email"]

            # Пользователь создаётся сразу, но неактивным
            user = User.objects.create(
                username=email,
                email=email,
                password=make_password(form.cleaned_data["password1"]),
                is_active=False,
            )
            app = TeacherApplication.objects.create(
                email=email,
                first_name=form.cleaned_data["first_name"],
                middle_name=form.cleaned_data["middle_name"],
                last_name=form.cleaned_data["last_name"],
                role=form.cleaned_data.get("role", ""),
                subject_tagline=form.cleaned_data.get("subject_tagline", ""),
                about=form.cleaned_data.get("about", ""),
            )
            app.desired_subjects.set(form.cleaned_data["subjects"])
            return render(request, "desk/register_done.html", {"email": email})
    else:
        form = TeacherRegisterForm()

    return render(request, "desk/register.html", {"form": form})


def approve_application(app: TeacherApplication, note=""):
    """Одобрение заявки: активирует пользователя, создаёт профиль, привязывает предметы."""
    from django.utils import timezone
    from django.utils.text import slugify
    import re as _re

    User = get_user_model()
    user = User.objects.get(username=app.email)

    # Код профиля из фамилии: petrova, при конфликте petrova2
    base = slugify(app.last_name, allow_unicode=False) or "teacher"
    base = _re.sub(r'[^a-z0-9-]', '', base)[:40] or "teacher"
    code, i = base, 2
    while TeacherProfile.objects.filter(code=code).exists():
        code = f"{base}{i}"
        i += 1

    user.is_active = True
    user.save(update_fields=["is_active"])

    profile = TeacherProfile.objects.create(
        user=user,
        first_name=app.first_name,
        middle_name=app.middle_name,
        last_name=app.last_name,
        code=code,
        role=app.role,
        bio=app.about,
        brand_tagline=app.subject_tagline,
    )
    profile.subjects.set(app.desired_subjects.all())

    app.status = TeacherApplication.Status.APPROVED
    app.reviewed_at = timezone.now()
    app.note = note
    app.save(update_fields=["status", "reviewed_at", "note"])
    return profile