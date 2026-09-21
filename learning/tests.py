"""
Testes de API do núcleo de aprendizagem — formaliza os cenários que
validei manualmente com curl: isolamento entre alunos, aprovação exclusiva
do professor, e o fluxo de tentativa de atividade.
"""
from rest_framework import status
from rest_framework.test import APITestCase

from subjects.models import Skill, Subject
from users.models import User

from .models import Diagnostic, StudyActivity, StudyPlan, TeacherFeedback


class DiagnosticAPITests(APITestCase):
    def setUp(self):
        self.aluno1 = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.aluno2 = User.objects.create_user(
            username="pedro", password="x", email="p@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="pr@t.com", role=User.Role.TEACHER)
        materia = Subject.objects.create(name="Matemática")
        skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno1)
        self.diagnostico = Diagnostic.objects.create(
            student=self.aluno1, skill=skill, mastery_level=40,
            difficulty_level="basic", evidence=["evidência de teste"])

    def test_aluno_ve_apenas_o_proprio_diagnostico(self):
        self.client.force_authenticate(user=self.aluno2)
        resp = self.client.get("/api/diagnostics/")
        self.assertEqual(resp.data["count"], 0)

        self.client.force_authenticate(user=self.aluno1)
        resp = self.client.get("/api/diagnostics/")
        self.assertEqual(resp.data["count"], 1)

    def test_professor_ve_todos_os_diagnosticos(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get("/api/diagnostics/")
        self.assertEqual(resp.data["count"], 1)

    def test_aluno_nao_pode_aprovar_proprio_diagnostico(self):
        self.client.force_authenticate(user=self.aluno1)
        resp = self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.diagnostico.refresh_from_db()
        self.assertEqual(self.diagnostico.status, Diagnostic.Status.PENDING)

    def test_professor_aprova_diagnostico(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.patch(f"/api/diagnostics/{self.diagnostico.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.diagnostico.refresh_from_db()
        self.assertEqual(self.diagnostico.status, Diagnostic.Status.APPROVED)
        self.assertEqual(self.diagnostico.validated_by, self.professor)
        self.assertIsNotNone(self.diagnostico.validated_at)

    def test_generate_funciona_de_verdade_desde_a_etapa_6(self):
        """Este teste verificava um stub 501 (Etapa 5); a partir da Etapa 6
        o endpoint gera diagnóstico de verdade. Sem AssessmentQuestion
        cadastrada para aluno1 aqui, o resultado esperado é sucesso com
        listas vazias — nunca 501 nem erro."""
        self.client.force_authenticate(user=self.aluno1)
        resp = self.client.post("/api/diagnostics/generate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["diagnostics"], [])
        self.assertEqual(resp.data["insufficient_evidence"], [])


class TeacherFeedbackAPITests(APITestCase):
    """Fecha a lacuna que o model TeacherFeedback tinha desde a Etapa 3
    (existia, nunca teve endpoint) — teste cobrindo criação, bloqueio de
    aluno, validação de rating e de diagnóstico↔aluno cruzado, e isolamento."""

    def setUp(self):
        self.aluno1 = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.aluno2 = User.objects.create_user(
            username="pedro", password="x", email="p@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="pr@t.com", role=User.Role.TEACHER)
        materia = Subject.objects.create(name="Matemática")
        skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno1, self.aluno2)
        self.diagnostico = Diagnostic.objects.create(
            student=self.aluno1, skill=skill, mastery_level=40,
            difficulty_level="basic", evidence=["teste"])

    def test_professor_cria_feedback(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/teacher-feedback/", {
            "student": self.aluno1.id, "diagnostic": self.diagnostico.id,
            "rating": 4, "comment": "Condiz com o que observo em sala.",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["teacher"], self.professor.id)  # nunca vem do corpo

    def test_aluno_nao_pode_criar_feedback(self):
        self.client.force_authenticate(user=self.aluno1)
        resp = self.client.post("/api/teacher-feedback/",
                                 {"student": self.aluno1.id, "rating": 5}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_rating_fora_do_intervalo_e_rejeitado(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/teacher-feedback/",
                                 {"student": self.aluno1.id, "rating": 9}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_diagnostico_de_outro_aluno_e_rejeitado(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/teacher-feedback/", {
            "student": self.aluno2.id, "diagnostic": self.diagnostico.id,  # é do aluno1
            "rating": 3,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_aluno_ve_so_o_proprio_feedback(self):
        TeacherFeedback.objects.create(teacher=self.professor, student=self.aluno1, rating=4)
        self.client.force_authenticate(user=self.aluno2)
        resp = self.client.get("/api/teacher-feedback/")
        self.assertEqual(resp.data["count"], 0)

        self.client.force_authenticate(user=self.aluno1)
        resp = self.client.get("/api/teacher-feedback/")
        self.assertEqual(resp.data["count"], 1)


class StudyPlanAPITests(APITestCase):
    """StudyPlan.approve nunca tinha ganhado teste formal — só foi
    conferido manualmente via curl na Etapa 5. Fechando essa lacuna aqui,
    já que a Seção 16 pede explicitamente 'apenas usuários autorizados
    possam modificar planos'."""

    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="pr@t.com", role=User.Role.TEACHER)
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno)
        self.plano = StudyPlan.objects.create(
            student=self.aluno, start_date="2026-01-01", end_date="2026-01-08")

    def test_aluno_nao_pode_aprovar_o_proprio_plano(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.patch(f"/api/study-plans/{self.plano.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.status, StudyPlan.Status.DRAFT)

    def test_professor_aprova_o_plano(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.patch(f"/api/study-plans/{self.plano.id}/approve/",
                                  {"status": "approved"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.status, StudyPlan.Status.APPROVED)

    def test_aluno_ainda_consegue_ler_o_proprio_plano(self):
        """A permissão bloqueia escrita (PATCH), nunca leitura (GET) do dono."""
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.get(f"/api/study-plans/{self.plano.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class StudyActivityAPITests(APITestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        outro_aluno = User.objects.create_user(
            username="pedro", password="x", email="p@t.com", role=User.Role.STUDENT)
        materia = Subject.objects.create(name="Matemática")
        skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        plano = StudyPlan.objects.create(student=self.aluno, start_date="2026-01-01", end_date="2026-01-08")
        self.atividade = StudyActivity.objects.create(
            study_plan=plano, skill=skill, title="Revisão", activity_type="review",
            difficulty="basic", estimated_minutes=20, order=1)

        plano_outro = StudyPlan.objects.create(student=outro_aluno, start_date="2026-01-01", end_date="2026-01-08")
        self.atividade_de_outro_aluno = StudyActivity.objects.create(
            study_plan=plano_outro, skill=skill, title="Revisão 2", activity_type="review",
            difficulty="basic", estimated_minutes=20, order=1)

    def test_aluno_nao_ve_atividade_de_outro_aluno(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.get(f"/api/activities/{self.atividade_de_outro_aluno.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_responder_atividade_cria_tentativa_e_completa_status(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.post(f"/api/activities/{self.atividade.id}/attempt/",
                                 {"answer": "1/2", "time_spent": 120}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.atividade.refresh_from_db()
        self.assertEqual(self.atividade.status, StudyActivity.Status.COMPLETED)
        self.assertEqual(self.atividade.attempts.count(), 1)
        self.assertEqual(self.atividade.attempts.first().student, self.aluno)
