"""
Disciplinas e Habilidades — inclui o Grafo de Conhecimento (prerequisites),
generalizando o que já validamos no sistema de automação escolar (lá era
um dict Python fixo; aqui vira dado do banco, editável pelo administrador
sem precisar mexer em código — Seção 3, perfil Administrador).
"""
from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    class DifficultyLevel(models.TextChoices):
        BASIC = "basic", "Básico"
        INTERMEDIATE = "intermediate", "Intermediário"
        ADVANCED = "advanced", "Avançado"

    class Stage(models.TextChoices):
        FUNDAMENTAL_II = "fundamental_ii", "Ensino Fundamental II"
        ENSINO_MEDIO = "ensino_medio", "Ensino Médio"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    difficulty_level = models.CharField(
        max_length=20, choices=DifficultyLevel.choices, default=DifficultyLevel.BASIC)
    # Opcionais, de propósito: nem toda Skill precisa estar amarrada a uma
    # série específica (ex.: habilidades genéricas/transversais). Quando
    # preenchido, permite filtrar o currículo por etapa/série sem precisar
    # de um model novo — o nome já vinha carregando essa informação como
    # texto livre ("Frações — 6º ano"); isso só torna filtrável de verdade.
    stage = models.CharField(max_length=20, choices=Stage.choices, blank=True)
    grade = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="6 a 9 para Fundamental II; 1 a 3 para Ensino Médio.")
    # Auto-referenciado e não-simétrico: se A é pré-requisito de B, isso não
    # implica que B é pré-requisito de A. Uma habilidade pode ter VÁRIOS
    # pré-requisitos (ex.: Sistemas de Equações depende de Equações do 1º
    # Grau E de Frações) — por isso M2M, não ForeignKey único. Nada impede
    # um pré-requisito de outra Subject — é assim que uma lacuna em Física
    # pode apontar pra causa raiz em Matemática (ver ai/diagnostic.py).
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="dependents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subject", "name"]
        unique_together = [("subject", "name")]

    def __str__(self) -> str:
        return f"{self.name} ({self.subject.name})"
