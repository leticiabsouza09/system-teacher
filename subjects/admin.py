from django.contrib import admin
from .models import Skill, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "difficulty_level", "updated_at")
    list_filter = ("subject", "difficulty_level")
    search_fields = ("name", "description")
    filter_horizontal = ("prerequisites",)
