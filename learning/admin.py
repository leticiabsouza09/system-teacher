from django.contrib import admin
from .models import (
    ActivityAttempt, Diagnostic, ProgressRecord, StudentSkill, StudyActivity,
    StudyPlan, TeacherFeedback,
)


@admin.register(StudentSkill)
class StudentSkillAdmin(admin.ModelAdmin):
    list_display = ("student", "skill", "mastery_level", "confidence", "last_evaluated_at")
    list_filter = ("skill__subject", "skill")
    search_fields = ("student__username", "skill__name")


@admin.register(Diagnostic)
class DiagnosticAdmin(admin.ModelAdmin):
    list_display = ("student", "skill", "mastery_level", "status", "created_at", "validated_by")
    list_filter = ("status", "difficulty_level", "skill__subject")
    search_fields = ("student__username", "skill__name")
    readonly_fields = ("created_at",)


class StudyActivityInline(admin.TabularInline):
    model = StudyActivity
    extra = 0


@admin.register(StudyPlan)
class StudyPlanAdmin(admin.ModelAdmin):
    list_display = ("student", "status", "created_by_ai", "start_date", "end_date", "created_at")
    list_filter = ("status", "created_by_ai")
    search_fields = ("student__username",)
    inlines = [StudyActivityInline]


@admin.register(StudyActivity)
class StudyActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "study_plan", "skill", "activity_type", "difficulty", "status", "order")
    list_filter = ("activity_type", "difficulty", "status")
    search_fields = ("title", "skill__name")


@admin.register(ActivityAttempt)
class ActivityAttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "activity", "score", "time_spent", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("student__username", "activity__title")


@admin.register(ProgressRecord)
class ProgressRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "skill", "mastery_before", "mastery_after", "source", "date")
    list_filter = ("source", "skill__subject")
    search_fields = ("student__username", "skill__name")


@admin.register(TeacherFeedback)
class TeacherFeedbackAdmin(admin.ModelAdmin):
    list_display = ("teacher", "student", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("teacher__username", "student__username", "comment")
