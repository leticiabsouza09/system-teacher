"""
Model de usuário customizado.

NOTA DE ARQUITETURA: o Django exige que AUTH_USER_MODEL aponte para um
model já existente antes da primeira migration — por isso esse model
mínimo é criado aqui, na Etapa 2 (Configuração/Banco), e não na Etapa 3
(Models), mesmo sendo tecnicamente um "model". A Etapa 3 usa este User
como base para os relacionamentos de StudentProfile/TeacherProfile e para
o restante do domínio (Subject, Skill, Assessment, etc.).
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Estende o AbstractUser do Django (que já traz username, password,
    first_name/last_name, email, is_active, date_joined) com o campo de
    papel (role) exigido pela Seção 3 do escopo (aluno/professor/admin)."""

    class Role(models.TextChoices):
        STUDENT = "student", "Aluno"
        TEACHER = "teacher", "Professor"
        ADMIN = "admin", "Administrador"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self) -> bool:
        return self.role == self.Role.TEACHER
