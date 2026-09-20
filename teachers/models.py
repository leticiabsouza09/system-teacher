"""Perfil do professor — hoje é só o vínculo com o User; cresce conforme
necessário (ex.: disciplinas que leciona) sem migration-quebra em cascata."""
from django.conf import settings
from django.db import models


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teacher_profile",
        limit_choices_to={"role": "teacher"},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Prof. {self.user}"
