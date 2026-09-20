from django.contrib import admin
from .models import Assessment, AssessmentQuestion


class AssessmentQuestionInline(admin.TabularInline):
    model = AssessmentQuestion
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "subject", "date", "score")
    list_filter = ("subject", "date")
    search_fields = ("title", "student__username")
    inlines = [AssessmentQuestionInline]
