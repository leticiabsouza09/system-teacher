from rest_framework import serializers

from users.models import User

from .models import ActivityAttempt, Diagnostic, ProgressRecord, StudyActivity, StudyPlan, TeacherFeedback


class DiagnosticSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)
    student_username = serializers.CharField(source="student.username", read_only=True)

    class Meta:
        model = Diagnostic
        fields = ["id", "student", "student_username", "skill", "skill_name", "mastery_level",
                  "difficulty_level", "evidence", "status", "created_at",
                  "validated_by", "validated_at"]
        read_only_fields = ["student", "skill", "mastery_level", "difficulty_level",
                             "evidence", "created_at", "validated_by", "validated_at"]
        # status É editável — é exatamente o que a action `approve` usa.
        # Tudo mais aqui só a IA (Etapa 6) escreve, nunca o cliente da API.


class DiagnosticApproveSerializer(serializers.Serializer):
    """Serializer só da action approve — aceita status e, opcionalmente,
    uma edição do mastery_level (o caso "professor edita antes de aprovar",
    Seção 3, que vira status=MODIFIED)."""
    status = serializers.ChoiceField(choices=[Diagnostic.Status.APPROVED, Diagnostic.Status.MODIFIED,
                                               Diagnostic.Status.REJECTED])
    mastery_level = serializers.IntegerField(required=False, min_value=0, max_value=100)
    teacher_notes = serializers.CharField(required=False, allow_blank=True)


class StudyActivitySerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = StudyActivity
        fields = ["id", "study_plan", "skill", "skill_name", "title", "description",
                  "activity_type", "difficulty", "estimated_minutes", "instructions",
                  "expected_answer", "explanation", "order", "status"]
        read_only_fields = ["study_plan", "skill", "title", "description", "activity_type",
                             "difficulty", "estimated_minutes", "instructions",
                             "expected_answer", "explanation", "order"]
        # De novo: só `status` é editável via API por fora da geração da IA
        # (ex.: aluno marca como "skipped"). O conteúdo em si vem só da IA.


class StudyPlanSerializer(serializers.ModelSerializer):
    activities = StudyActivitySerializer(many=True, read_only=True)
    student_username = serializers.CharField(source="student.username", read_only=True)

    class Meta:
        model = StudyPlan
        fields = ["id", "student", "student_username", "created_by_ai", "status",
                  "start_date", "end_date", "teacher_notes", "activities",
                  "created_at", "updated_at"]
        read_only_fields = ["student", "created_by_ai", "start_date", "end_date",
                             "created_at", "updated_at"]
        # status e teacher_notes são editáveis (aprovação/observações do
        # professor); o resto só a IA gera.


class ActivityAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityAttempt
        fields = ["id", "activity", "student", "answer", "score", "time_spent", "completed_at"]
        read_only_fields = ["student", "score", "completed_at"]
        # score nunca vem do cliente — Etapa 8 (adaptação) é quem calcula
        # a partir de expected_answer/correção automática ou correção da IA.


class ActivityAttemptCreateSerializer(serializers.Serializer):
    """Usado só na action `attempt` — o aluno manda a resposta e o tempo
    gasto; o resto (quem é o aluno, a nota, o horário) o servidor decide."""
    answer = serializers.CharField(allow_blank=True)
    time_spent = serializers.IntegerField(min_value=0)


class ProgressRecordSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)
    student_username = serializers.CharField(source="student.username", read_only=True)

    class Meta:
        model = ProgressRecord
        fields = ["id", "student", "student_username", "skill", "skill_name",
                  "mastery_before", "mastery_after", "date", "source"]
        read_only_fields = fields


class TeacherFeedbackSerializer(serializers.ModelSerializer):
    """`teacher` é sempre request.user (nunca confiar no corpo da
    requisição — mesmo padrão de mass-assignment protection usado em
    AssessmentSerializer). `rating` tem limite explícito 1-5 aqui porque
    o model usa PositiveSmallIntegerField, que sozinho não impede um 6
    ou um 500."""
    teacher_username = serializers.CharField(source="teacher.username", read_only=True)
    student_username = serializers.CharField(source="student.username", read_only=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = TeacherFeedback
        fields = ["id", "teacher", "teacher_username", "student", "student_username",
                  "diagnostic", "rating", "comment", "created_at"]
        read_only_fields = ["teacher", "created_at"]

    def validate_student(self, value):
        if value.role != User.Role.STUDENT:
            raise serializers.ValidationError("O destinatário do feedback precisa ser um aluno.")
        request = self.context.get("request")
        if request and request.user.is_teacher:
            from core.permissions import teacher_has_classroom_with
            if not teacher_has_classroom_with(request.user, value):
                raise serializers.ValidationError(
                    "Você só pode registrar anotações sobre alunos das suas turmas.")
        return value

    def validate(self, attrs):
        diagnostico = attrs.get("diagnostic")
        aluno = attrs.get("student")
        if diagnostico and aluno and diagnostico.student_id != aluno.id:
            raise serializers.ValidationError(
                {"diagnostic": "Este diagnóstico não pertence ao aluno informado."})
        return attrs
