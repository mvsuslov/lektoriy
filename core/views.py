from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .forms import AttachmentForm, LinkForm, TeacherMaterialForm
from django.core.paginator import Paginator
from django.db.models import Count, Q

from .models import Material, Subject, TeacherProfile

PER_PAGE = 6


def public_materials():
    """Опубликованные материалы не из скрытых предметов."""
    return Material.objects.filter(
        is_published=True, subject__is_hidden=False
    ).select_related("subject", "author")


def portal_home(request):
    recent = public_materials().order_by("-created_at")[:6]  # ← свежие слева
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
    return render(request, "portal/subjects.html")


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
    return render(request, "portal/material.html", {"material": material})


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

    # Алфавитные диапазоны — только по фамилиям, пустые не показываем
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

    view_mode = request.GET.get("view", "recent")  # 'recent' или 'all'
    return render(request, "teacher/home.html", {
        "teacher": teacher,
        "recent": base.order_by("-created_at")[:6],
        "materials": base.order_by("created_at"),
        "public_subjects": teacher.subjects.filter(is_hidden=False),
        "view_mode": view_mode,
    })


def teacher_subject(request, code, subject_slug):
    teacher = get_object_or_404(TeacherProfile, code=code)
    subject = get_object_or_404(Subject, slug=subject_slug)
    if not teacher.subjects.filter(pk=subject.pk).exists():
        return render(request, "404.html", status=404)

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
    
    
def get_teacher(request):
    return getattr(request.user, "teacher_profile", None)


@login_required
def desk_home(request):
    """Простой кабинет преподавателя: список его материалов + кнопка публикации."""
    teacher = get_teacher(request)
    if not teacher:
        messages.error(request, "У вашей учётной записи нет профиля преподавателя. "
                                "Обратитесь к администратору портала.")
        return redirect("portal_home")
    materials = teacher.materials.select_related("subject")
    return render(request, "desk/home.html", {
        "teacher": teacher,
        "materials": materials,
    })


@login_required
def desk_material_new(request):
    """Публикация нового материала — минимум действий."""
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


@login_required
def desk_material_toggle(request, pk):
    """Быстрое снятие с публикации / публикация."""
    teacher = get_teacher(request)
    material = get_object_or_404(Material, pk=pk)
    if not request.user.is_superuser and material.author != teacher:
        return redirect("desk_home")
    material.is_published = not material.is_published
    material.save(update_fields=["is_published"])
    return redirect("desk_home")
