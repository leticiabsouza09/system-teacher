from rest_framework import serializers

from learning.models import Diagnostic, StudyPlan
from users.models import User


class StudentSkillSummarySerializer(serializers.Serializer):
    skill = serializers.CharField()
    mastery_level = serializers.IntegerField()


class StudentDashboardSerializer(serializers.Serializer):
    """Não é ModelSerializer — é um agregado de várias fontes (Seção 10),
    então o formato é definido aqui, não a partir de um único model."""
    progress_overall = serializers.FloatField()
    activities_completed = serializers.IntegerField()
    study_time_minutes = serializers.IntegerField()
    skills_mastered = StudentSkillSummarySerializer(many=True)
    skills_developing = StudentSkillSummarySerializer(many=True)
    current_plan = serializers.DictField(allow_null=True)


class TeacherStudentSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    progress_overall = serializers.FloatField()
    pending_diagnostics = serializers.IntegerField()


class PersistentAlertSerializer(serializers.Serializer):
    student = serializers.CharField()
    skill = serializers.CharField()
    evidence = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class TeacherDashboardSerializer(serializers.Serializer):
    students = TeacherStudentSummarySerializer(many=True)
    pending_diagnostics_count = serializers.IntegerField()
    plans_awaiting_approval_count = serializers.IntegerField()
    persistent_difficulty_alerts = PersistentAlertSerializer(many=True)
