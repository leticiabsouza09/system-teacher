"""Perfil do aluno — dados que não pertencem ao User genérico (auth)."""
from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile",
        limit_choices_to={"role": "student"},
    )
    date_of_birth = models.DateField(null=True, blank=True)
    grade_level = models.CharField(max_length=50, help_text="Ex.: '8º ano', '2º ano EM'")
    study_time_available = models.PositiveIntegerField(
        default=30, help_text="Minutos disponíveis por dia para estudo")
    learning_preferences = models.JSONField(
        default=dict, blank=True,
        help_text="Ex.: {'formato_preferido': 'exercicios_praticos', 'melhor_horario': 'manha'}")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Perfil de {self.user}"
