"""Testes de model + API de assessments — inclui o isolamento aluno↔aluno
que só tinha sido validado manualmente (curl) até agora."""
from rest_framework import status
from rest_framework.test import APITestCase

from subjects.models import Skill, Subject
from users.models import User

from .models import Assessment, AssessmentQuestion


class AssessmentModelTests(APITestCase):
    def setUp(self):
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=self.materia, name="Frações", difficulty_level="basic")

    def test_criacao_e_relacionamento_com_questoes(self):
        av = Assessment.objects.create(
            student=self.aluno, subject=self.materia, title="Prova 1", date="2026-01-01", score=70)
        AssessmentQuestion.objects.create(
            assessment=av, skill=self.skill, question="Quanto é 1/2?", correct_answer="0.5",
            student_answer="0.5", is_correct=True)
        self.assertEqual(av.questions.count(), 1)
        self.assertEqual(av.questions.first().skill, self.skill)


class AssessmentAPITests(APITestCase):
    def setUp(self):
        self.aluno1 = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.aluno2 = User.objects.create_user(
            username="pedro", password="x", email="p@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="pr@t.com", role=User.Role.TEACHER)
        self.materia = Subject.objects.create(name="Matemática")
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno1)
        Assessment.objects.create(
            student=self.aluno1, subject=self.materia, title="Prova de Joana",
            date="2026-01-01", score=70)

    def test_aluno_nao_ve_avaliacao_de_outro_aluno(self):
        self.client.force_authenticate(user=self.aluno2)
        resp = self.client.get("/api/assessments/")
        self.assertEqual(resp.data["count"], 0)

    def test_professor_ve_todas_as_avaliacoes(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get("/api/assessments/")
        self.assertEqual(resp.data["count"], 1)

    def test_aluno_criando_avaliacao_nao_consegue_atribuir_a_outro_aluno(self):
        """O campo `student` é read_only no serializer — mesmo mandando o
        id de outro aluno no corpo, a avaliação deve ficar em nome de quem
        está autenticado."""
        self.client.force_authenticate(user=self.aluno2)
        resp = self.client.post("/api/assessments/", {
            "student": self.aluno1.id,  # tentativa de forjar o dono
            "subject": self.materia.id, "title": "Forjada", "date": "2026-01-01", "score": 100,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["student"], self.aluno2.id)  # nunca aluno1
