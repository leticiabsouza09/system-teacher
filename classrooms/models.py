"""
Turma — o vínculo real entre professor e aluno que faltava desde a Etapa 4.

Antes deste model, "professor vê todos os alunos" era uma simplificação
documentada (não existia nenhum jeito de restringir por vínculo real). A
partir daqui, um professor só acessa/gerencia dados de alunos que estão
numa Turma que ele leciona — em todos os pontos que antes diziam "qualquer
professor vê qualquer aluno" (ver core/permissions.py, students/views.py,
learning/views.py, assessments/views.py, dashboard/views.py).

Administrador continua vendo tudo, sem essa restrição — corresponde ao
papel dele no sistema (Seção 3: "gerenciar usuários... visualizar
métricas gerais").
"""
from django.conf import settings
from django.db import models


class Classroom(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Ex.: '8º Ano A - Matutino'")
    teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="classrooms_teaching",
        limit_choices_to={"role": "teacher"}, blank=True)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="classrooms_enrolled",
        limit_choices_to={"role": "student"}, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
