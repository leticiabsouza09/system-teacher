"""
App `pedagogico` — boletim/frequência do dia a dia do professor.

Integrado ao System Teacher: NÃO tem Aluno/Turma/Disciplina próprios.
`aluno` é sempre `users.User` (role=student); turma é sempre
`classrooms.Classroom` (via `aluno.classrooms_enrolled`, não guardado
aqui); disciplina é sempre `subjects.Subject`. Isso evita duas
identidades paralelas pro mesmo aluno — a versão standalone deste app
tinha um model `Aluno` próprio, sem login, que teria duplicado
`users.User` se copiada direto pra cá.

`bimestre` em RegistroFrequencia continua existindo (mesma razão da
versão standalone): sem ele, calcular frequência "no bimestre X" exigiria
inferir uma faixa de datas por bimestre, suposição de calendário que
ninguém informou.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from subjects.models import Subject

BIMESTRE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(4)]


class LancamentoNota(models.Model):
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lancamentos_nota",
        limit_choices_to={"role": "student"})
    disciplina = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="lancamentos_nota")
    bimestre = models.PositiveSmallIntegerField(validators=BIMESTRE_VALIDATORS)
    nota = models.DecimalField(
        max_digits=3, decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("aluno", "disciplina", "bimestre")]
        indexes = [models.Index(fields=["aluno", "bimestre"])]

    def __str__(self) -> str:
        return f"{self.aluno_id} · {self.disciplina} · B{self.bimestre}: {self.nota}"


class RegistroFrequencia(models.Model):
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registros_frequencia",
        limit_choices_to={"role": "student"})
    disciplina = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="registros_frequencia")
    data = models.DateField()
    bimestre = models.PositiveSmallIntegerField(validators=BIMESTRE_VALIDATORS)
    presente = models.BooleanField(default=True)

    class Meta:
        unique_together = [("aluno", "disciplina", "data")]
        indexes = [models.Index(fields=["aluno", "disciplina", "bimestre"])]

    def __str__(self) -> str:
        status = "presente" if self.presente else "ausente"
        return f"{self.aluno_id} · {self.disciplina} · {self.data}: {status}"


class ParecerPedagogico(models.Model):
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pareceres_pedagogicos",
        limit_choices_to={"role": "student"})
    bimestre = models.PositiveSmallIntegerField(validators=BIMESTRE_VALIDATORS)
    causa_raiz = models.TextField()
    acao_recomendada = models.TextField()
    aprovado_pelo_professor = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("aluno", "bimestre")]

    def __str__(self) -> str:
        return f"Parecer {self.aluno_id} · B{self.bimestre}"
