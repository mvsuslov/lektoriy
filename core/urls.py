from django.urls import path
from . import views

urlpatterns = [
    path("", views.portal_home, name="portal_home"),
    path("subjects/", views.all_subjects, name="all_subjects"),
    path("subjects/<slug:slug>/", views.subject_detail, name="subject_detail"),
    path("subjects/<slug:slug>/materials/<slug:material_slug>/",
         views.material_detail, name="material_detail"),
    path("teachers/", views.teachers_list, name="teachers_list"),
    path("t/<slug:code>/", views.teacher_home, name="teacher_home"),
    path("t/<slug:code>/<slug:subject_slug>/", views.teacher_subject,
         name="teacher_subject"),
    path("search/", views.search, name="search"),
    path("desk/", views.desk_home, name="desk_home"),
    path("desk/new/", views.desk_material_new, name="desk_material_new"),
    path("desk/toggle/<int:pk>/", views.desk_material_toggle, name="desk_material_toggle"),
    path("desk/password/", views.desk_password, name="desk_password"),

]
