from rest_framework import serializers

from .models import Assessment, AssessmentQuestion


class AssessmentQuestionSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = AssessmentQuestion
        fields = ["id", "assessment", "skill", "skill_name", "question",
                  "correct_answer", "student_answer", "is_correct"]


class AssessmentSerializer(serializers.ModelSerializer):
    questions = AssessmentQuestionSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Assessment
        fields = ["id", "student", "subject", "subject_name", "title", "date", "score", "questions"]
        read_only_fields = ["student"]  # setado automaticamente a partir do request, nunca do body

    def create(self, validated_data):
        # Aluno só cria avaliação em nome dele mesmo — mesmo que tente
        # mandar outro "student" no corpo da requisição, ignoramos (o
        # campo é read_only) e usamos sempre request.user.
        validated_data["student"] = self.context["request"].user
        return super().create(validated_data)
