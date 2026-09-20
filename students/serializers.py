from rest_framework import serializers

from users.models import User

from .models import StudentProfile


class StudentSerializer(serializers.ModelSerializer):
    """Representa o Aluno como o endpoint /api/students/ o expõe — dados
    do User + do StudentProfile combinados, porque para quem consome a
    API os dois formam um único conceito ("o aluno")."""
    grade_level = serializers.CharField(source="student_profile.grade_level", default=None)
    study_time_available = serializers.IntegerField(
        source="student_profile.study_time_available", default=None)
    learning_preferences = serializers.JSONField(
        source="student_profile.learning_preferences", default=dict)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name",
                  "grade_level", "study_time_available", "learning_preferences"]
        read_only_fields = fields


class StudentSkillSerializer(serializers.Serializer):
    """Serializer simples (não ModelSerializer) usado só na action
    /students/{id}/skills/ — importa o model de `learning` aqui dentro, e
    não no topo do arquivo, para não criar dependência circular entre
    apps (students não deveria depender de aprendizagem em geral)."""
    skill = serializers.CharField(source="skill.name")
    subject = serializers.CharField(source="skill.subject.name")
    mastery_level = serializers.IntegerField()
    confidence = serializers.FloatField()
    last_evaluated_at = serializers.DateTimeField()


class ProgressRecordSerializer(serializers.Serializer):
    skill = serializers.CharField(source="skill.name")
    mastery_before = serializers.IntegerField()
    mastery_after = serializers.IntegerField()
    date = serializers.DateTimeField()
    source = serializers.CharField()
