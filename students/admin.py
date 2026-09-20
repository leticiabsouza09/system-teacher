from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "grade_level", "study_time_available", "updated_at")
    list_filter = ("grade_level",)
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
