"""
Núcleo do domínio de aprendizagem: domínio de habilidade por aluno,
diagnóstico gerado pela IA (com aprovação humana obrigatória — Seção 1),
plano de estudo, atividades, tentativas, progresso e feedback docente.
"""
from django.conf import settings
from django.db import models

from subjects.models import Skill


class StudentSkill(models.Model):
    """Nível de domínio ATUAL do aluno numa habilidade — é o "estado",
    atualizado a cada nova evidência (avaliação, atividade). Diferente de
    ProgressRecord, que é o HISTÓRICO de como esse estado mudou ao longo
    do tempo."""
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_states",
        limit_choices_to={"role": "student"},
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="student_states")
    mastery_level = models.PositiveSmallIntegerField(
        default=0, help_text="Escala de 0 a 100")
    confidence = models.FloatField(
        default=0.5, help_text="0.0 a 1.0 — quão confiável é essa estimativa (poucos dados = baixa)")
    last_evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("student", "skill")]
        ordering = ["student", "skill"]

    def __str__(self) -> str:
        return f"{self.student} — {self.skill.name}: {self.mastery_level}%"


class Diagnostic(models.Model):
    """Uma PROPOSTA de diagnóstico gerada pela IA para uma habilidade
    específica — nunca vale por si só. Só quando status vira APPROVED (ou
    MODIFIED, quando o professor edita antes de aprovar) é que o resto do
    sistema (geração de plano) pode agir sobre ele. Ver Seção 1: a IA é
    apoio à decisão, o professor é quem decide de fato."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        MODIFIED = "modified", "Modificado pelo professor"
        REJECTED = "rejected", "Rejeitado"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diagnostics",
        limit_choices_to={"role": "student"},
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="diagnostics")
    mastery_level = models.PositiveSmallIntegerField(help_text="Estimativa da IA, 0-100")
    difficulty_level = models.CharField(max_length=20, choices=Skill.DifficultyLevel.choices)
    evidence = models.JSONField(
        default=list,
        help_text="Lista de strings — cada evidência concreta que embasou o diagnóstico. "
                   "Nunca fica vazia quando status != PENDING sem justificativa de dado insuficiente.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="validated_diagnostics", limit_choices_to={"role": "teacher"},
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Diagnóstico {self.skill.name} — {self.student} [{self.get_status_display()}]"


class StudyPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho (proposta da IA)"
        APPROVED = "approved", "Aprovado pelo professor"
        ACTIVE = "active", "Em andamento"
        COMPLETED = "completed", "Concluído"
        ARCHIVED = "archived", "Arquivado"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_plans",
        limit_choices_to={"role": "student"},
    )
    created_by_ai = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    end_date = models.DateField()
    teacher_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Plano de {self.student} ({self.start_date} a {self.end_date})"


class StudyActivity(models.Model):
    class ActivityType(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice", "Múltipla escolha"
        TRUE_FALSE = "true_false", "Verdadeiro ou falso"
        SHORT_ANSWER = "short_answer", "Resposta curta"
        PROBLEM_SOLVING = "problem_solving", "Resolução de problemas"
        PRACTICAL_EXERCISE = "practical_exercise", "Exercício prático"
        CHALLENGE = "challenge", "Desafio"
        REVIEW = "review", "Revisão"
        MINI_ASSESSMENT = "mini_assessment", "Miniavaliação"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluída"
        SKIPPED = "skipped", "Pulada"

    study_plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="activities")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=30, choices=ActivityType.choices)
    difficulty = models.CharField(max_length=20, choices=Skill.DifficultyLevel.choices)
    estimated_minutes = models.PositiveIntegerField()
    instructions = models.TextField(blank=True)
    expected_answer = models.TextField(blank=True)
    explanation = models.TextField(
        blank=True, help_text="Mostrada ao aluno depois de responder — Seção 7")
    order = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["study_plan", "order"]
        verbose_name_plural = "Study Activities"

    def __str__(self) -> str:
        return f"{self.order}. {self.title} ({self.study_plan})"


class ActivityAttempt(models.Model):
    activity = models.ForeignKey(StudyActivity, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_attempts",
        limit_choices_to={"role": "student"},
    )
    answer = models.TextField(blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, help_text="0 a 100")
    time_spent = models.PositiveIntegerField(help_text="Segundos")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]

    def __str__(self) -> str:
        return f"Tentativa de {self.student} em {self.activity} — {self.score}%"


class ProgressRecord(models.Model):
    """Histórico de EVOLUÇÃO de mastery_level — cada linha é um "antes/
    depois" datado, o que alimenta os gráficos do dashboard (Seção 9/10).
    StudentSkill.mastery_level é sempre o valor mais recente; este model
    é a série temporal completa."""
    class Source(models.TextChoices):
        ASSESSMENT = "assessment", "Avaliação"
        ACTIVITY = "activity", "Atividade"
        MANUAL_TEACHER = "manual_teacher", "Ajuste manual do professor"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress_records",
        limit_choices_to={"role": "student"},
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="progress_records")
    mastery_before = models.PositiveSmallIntegerField()
    mastery_after = models.PositiveSmallIntegerField()
    date = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20, choices=Source.choices)

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.student} — {self.skill.name}: {self.mastery_before}%→{self.mastery_after}%"


class TeacherFeedback(models.Model):
    """Feedback do professor sobre um diagnóstico específico — é o que
    alimenta a métrica de 'concordância docente' (Seção 15)."""
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_given",
        limit_choices_to={"role": "teacher"},
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_received",
        limit_choices_to={"role": "student"},
    )
    diagnostic = models.ForeignKey(
        Diagnostic, on_delete=models.CASCADE, related_name="feedback", null=True, blank=True)
    rating = models.PositiveSmallIntegerField(help_text="1 a 5")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Feedback de {self.teacher} sobre {self.student} — nota {self.rating}"
