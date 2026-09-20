"""Testes de model — criação, relacionamentos e validações (Seção 16)."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Skill, Subject


class SubjectModelTests(TestCase):
    def test_criacao_basica(self):
        materia = Subject.objects.create(name="Matemática", description="Números e operações")
        self.assertEqual(str(materia), "Matemática")

    def test_nome_duplicado_nao_permitido(self):
        Subject.objects.create(name="Matemática")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Subject.objects.create(name="Matemática")


class SkillModelTests(TestCase):
    def setUp(self):
        self.materia = Subject.objects.create(name="Matemática")

    def test_criacao_e_relacionamento_com_subject(self):
        skill = Skill.objects.create(subject=self.materia, name="Frações", difficulty_level="basic")
        self.assertEqual(skill.subject, self.materia)
        self.assertIn(skill, self.materia.skills.all())

    def test_grafo_de_prerequisitos_bidirecional(self):
        fracoes = Skill.objects.create(subject=self.materia, name="Frações", difficulty_level="basic")
        equacoes = Skill.objects.create(subject=self.materia, name="Equações", difficulty_level="intermediate")
        sistemas = Skill.objects.create(subject=self.materia, name="Sistemas", difficulty_level="advanced")
        sistemas.prerequisites.set([fracoes, equacoes])

        self.assertEqual(set(sistemas.prerequisites.all()), {fracoes, equacoes})
        self.assertEqual(set(fracoes.dependents.all()), {sistemas})
        # Não-simétrico: fracoes NÃO tem sistemas como pré-requisito
        self.assertEqual(list(fracoes.prerequisites.all()), [])

    def test_mesmo_nome_em_disciplinas_diferentes_e_permitido(self):
        outra_materia = Subject.objects.create(name="Física")
        Skill.objects.create(subject=self.materia, name="Vetores", difficulty_level="basic")
        # Não deve levantar erro — unique_together é (subject, name), não só name
        Skill.objects.create(subject=outra_materia, name="Vetores", difficulty_level="basic")
        self.assertEqual(Skill.objects.filter(name="Vetores").count(), 2)

    def test_mesmo_nome_na_mesma_disciplina_nao_permitido(self):
        Skill.objects.create(subject=self.materia, name="Frações", difficulty_level="basic")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Skill.objects.create(subject=self.materia, name="Frações", difficulty_level="basic")
