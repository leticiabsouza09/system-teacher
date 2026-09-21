from django.contrib import admin

from .models import Classroom


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher_count", "student_count", "updated_at")
    search_fields = ("name", "teachers__username", "students__username")
    filter_horizontal = ("teachers", "students")

    def teacher_count(self, obj):
        return obj.teachers.count()
    teacher_count.short_description = "Professores"

    def student_count(self, obj):
        return obj.students.count()
    student_count.short_description = "Alunos"
