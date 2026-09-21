"""
Testes do model Classroom e do isolamento real que ele impõe — a parte
que prova que "professor só vê aluno da própria turma" funciona de
verdade, não só que "professor com turma vê seu aluno" (isso os outros
apps já testam nos próprios setUp). Aqui o foco é o caso negativo: um
professor SEM vínculo não deveria conseguir nada.
"""
from rest_framework.test import APITestCase

from assessments.models import Assessment
from core.permissions import teacher_has_classroom_with
from learning.models import Diagnostic
from subjects.models import Skill, Subject
from users.models import User

from .models import Classroom


class ClassroomModelTests(APITestCase):
    def test_criacao_e_relacionamento_m2m(self):
        professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        turma = Classroom.objects.create(name="8º Ano A")
        turma.teachers.add(professor)
        turma.students.add(aluno)

        self.assertIn(turma, professor.classrooms_teaching.all())
        self.assertIn(turma, aluno.classrooms_enrolled.all())

    def test_teacher_has_classroom_with_positivo_e_negativo(self):
        professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        aluno_da_turma = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        aluno_de_fora = User.objects.create_user(
            username="pedro", password="x", email="p2@t.com", role=User.Role.STUDENT)
        turma = Classroom.objects.create(name="8º Ano A")
        turma.teachers.add(professor)
        turma.students.add(aluno_da_turma)

        self.assertTrue(teacher_has_classroom_with(professor, aluno_da_turma))
        self.assertFalse(teacher_has_classroom_with(professor, aluno_de_fora))


class ClassroomIsolationAPITests(APITestCase):
    """Professor SEM vínculo de turma com o aluno — todo endpoint
    relevante deve bloquear, não só listar vazio silenciosamente onde
    fizer sentido dar 403/404 explícito."""

    def setUp(self):
        self.professor_vinculado = User.objects.create_user(
            username="prof_vinculado", password="x", email="pv@t.com", role=User.Role.TEACHER)
        self.professor_de_fora = User.objects.create_user(
            username="prof_de_fora", password="x", email="pf@t.com", role=User.Role.TEACHER)
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)

        turma = Classroom.objects.create(name="8º Ano A")
        turma.teachers.add(self.professor_vinculado)
        turma.students.add(self.aluno)  # professor_de_fora NUNCA entra aqui

        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        self.diagnostico = Diagnostic.objects.create(
            student=self.aluno, skill=self.skill, mastery_level=30,
            difficulty_level="basic", evidence=["teste"])
        Assessment.objects.create(student=self.aluno, subject=materia, title="Prova", date="2026-01-01", score=50)

    def test_professor_de_fora_nao_ve_o_aluno_na_listagem(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.get("/api/students/")
        self.assertEqual(resp.data["count"], 0)

    def test_professor_de_fora_nao_ve_diagnostico_do_aluno(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.get("/api/diagnostics/")
        self.assertEqual(resp.data["count"], 0)

    def test_professor_de_fora_nao_ve_avaliacao_do_aluno(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.get("/api/assessments/")
        self.assertEqual(resp.data["count"], 0)

    def test_professor_de_fora_nao_consegue_aprovar_diagnostico(self):
        """404, não 403: get_queryset() já filtra o diagnóstico pra fora
        do alcance do professor sem vínculo, antes de qualquer permissão
        de objeto rodar — mesmo padrão já usado no isolamento aluno↔aluno
        (não revela nem que o diagnóstico existe)."""
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.diagnostico.refresh_from_db()
        self.assertEqual(self.diagnostico.status, Diagnostic.Status.PENDING)

    def test_professor_vinculado_consegue_aprovar(self):
        self.client.force_authenticate(user=self.professor_vinculado)
        resp = self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_professor_de_fora_nao_gera_diagnostico_para_o_aluno(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.post("/api/diagnostics/generate/", {"student": self.aluno.id}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_professor_de_fora_nao_ve_dashboard_com_o_aluno(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.get("/api/dashboard/teacher/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["students"], [])

    def test_professor_de_fora_nao_registra_anotacao_sobre_o_aluno(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.post("/api/teacher-feedback/",
                                 {"student": self.aluno.id, "rating": 3}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("student", resp.data)
