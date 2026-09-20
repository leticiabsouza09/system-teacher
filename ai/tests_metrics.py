"""Testes do ProgressAnalyzerService (Etapa 15/Métricas). Nome do arquivo
separado de tests.py e tests_activity_and_adaptation.py, todos descobertos
pelo runner padrão (test*.py)."""
from django.test import TestCase
from rest_framework.test import APITestCase

from assessments.models import Assessment, AssessmentQuestion
from learning.models import (
    ActivityAttempt, Diagnostic, ProgressRecord, StudentSkill, StudyActivity, StudyPlan,
    TeacherFeedback,
)
from subjects.models import Skill, Subject
from users.models import User

from .progress_analyzer import ProgressAnalyzerService


class ProgressAnalyzerEmptyDatabaseTests(TestCase):
    """Banco vazio: TODAS as métricas precisam vir como not_implemented,
    nunca um 0 fingindo ser um resultado real — exceto
    intervencoes_obrigatorias_do_professor, que É um count legítimo de
    zero (ausência real de intervenções, não falta de dado)."""

    def test_nenhuma_metrica_calculavel_inventa_zero(self):
        resultado = ProgressAnalyzerService().compute_all()
        for categoria, metricas in resultado.items():
            for nome, m in metricas.items():
                if nome == "intervencoes_obrigatorias_do_professor":
                    continue
                self.assertIsNone(m["value"], f"{categoria}.{nome} deveria ser None com banco vazio")
                self.assertIsNotNone(m["not_implemented"], f"{categoria}.{nome} sem motivo declarado")

    def test_intervencoes_e_zero_de_verdade_nao_indisponivel(self):
        resultado = ProgressAnalyzerService().compute_all()
        m = resultado["seguranca_e_equidade"]["intervencoes_obrigatorias_do_professor"]
        self.assertEqual(m["value"], 0)
        self.assertIsNone(m["not_implemented"])


class ProgressAnalyzerCalculationTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")

    def test_ganho_medio_aprendizagem(self):
        ProgressRecord.objects.create(student=self.aluno, skill=self.skill,
                                       mastery_before=20, mastery_after=40, source="assessment")
        ProgressRecord.objects.create(student=self.aluno, skill=self.skill,
                                       mastery_before=40, mastery_after=80, source="activity")
        m = ProgressAnalyzerService().ganho_medio_aprendizagem()
        self.assertEqual(m["value"], 30.0)

    def test_percentual_objetivos_dominados(self):
        StudentSkill.objects.create(student=self.aluno, skill=self.skill, mastery_level=80)
        skill2 = Skill.objects.create(subject=self.skill.subject, name="Geometria", difficulty_level="basic")
        StudentSkill.objects.create(student=self.aluno, skill=skill2, mastery_level=50)
        m = ProgressAnalyzerService().percentual_objetivos_dominados()
        self.assertEqual(m["value"], 0.5)  # 1 de 2 >= 70

    def test_concordancia_docente_ignora_pendentes(self):
        Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                   difficulty_level="basic", evidence=["e"],
                                   status=Diagnostic.Status.APPROVED)
        Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                   difficulty_level="basic", evidence=["e"],
                                   status=Diagnostic.Status.MODIFIED)
        Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                   difficulty_level="basic", evidence=["e"],
                                   status=Diagnostic.Status.PENDING)  # não deve entrar na conta
        m = ProgressAnalyzerService().concordancia_docente()
        self.assertEqual(m["value"], 0.5)  # 1 approved de 2 avaliados (pending fora)

    def test_cobertura_das_lacunas(self):
        diag = Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                          difficulty_level="basic", evidence=["e"])
        plano = StudyPlan.objects.create(student=self.aluno, start_date="2026-01-01", end_date="2026-01-08")
        StudyActivity.objects.create(study_plan=plano, skill=self.skill, title="A", activity_type="review",
                                      difficulty="basic", estimated_minutes=15, order=1)
        m = ProgressAnalyzerService().cobertura_das_lacunas()
        self.assertEqual(m["value"], 1.0)  # a única lacuna virou atividade

    def test_precisao_diagnostica_e_marcada_como_proxy(self):
        diag = Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                          difficulty_level="basic", evidence=["e"])
        TeacherFeedback.objects.create(teacher=self.professor, student=self.aluno,
                                        diagnostic=diag, rating=5)
        m = ProgressAnalyzerService().precisao_diagnostica()
        self.assertEqual(m["value"], 1.0)  # (5-1)/4 = 1.0
        self.assertTrue(m["proxy"])  # precisa vir marcado como aproximação

    def test_quantidade_de_ajustes(self):
        Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                   difficulty_level="basic", evidence=["e"],
                                   status=Diagnostic.Status.MODIFIED)
        Diagnostic.objects.create(student=self.aluno, skill=self.skill, mastery_level=30,
                                   difficulty_level="basic", evidence=["e"],
                                   status=Diagnostic.Status.APPROVED)
        m = ProgressAnalyzerService().quantidade_de_ajustes()
        self.assertEqual(m["value"], 0.5)


class SystemMetricsAPITests(APITestCase):
    def setUp(self):
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)

    def test_aluno_nao_acessa_metricas_do_sistema(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.get("/api/dashboard/metrics/")
        self.assertEqual(resp.status_code, 403)

    def test_professor_acessa_metricas(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get("/api/dashboard/metrics/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("aprendizagem", resp.data)
        self.assertIn("qualidade_da_ia", resp.data)
        self.assertIn("engajamento", resp.data)
        self.assertIn("eficiencia_docente", resp.data)
        self.assertIn("seguranca_e_equidade", resp.data)
