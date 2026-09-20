"""Avaliações e as questões individuais que as compõem (nível de
granularidade necessário para o diagnóstico por habilidade, não só nota
agregada — mesma lição aprendida no sistema escolar: causa raiz por
micro-habilidade exige dado item-a-item, não só a nota final)."""
from django.conf import settings
from django.db import models

from subjects.models import Subject, Skill


class Assessment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessments",
        limit_choices_to={"role": "student"},
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assessments")
    title = models.CharField(max_length=200)
    date = models.DateField()
    score = models.DecimalField(max_digits=5, decimal_places=2, help_text="0 a 100")

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.title} — {self.student} ({self.date})"


class AssessmentQuestion(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="assessment_questions")
    question = models.TextField()
    correct_answer = models.TextField()
    student_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, help_text="Null = ainda não corrigida")

    def __str__(self) -> str:
        return f"Questão de {self.skill.name} — {self.assessment}"
