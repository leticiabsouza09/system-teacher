"""Testes de model + API — inclui o isolamento aluno↔aluno no /api/students/
e nas actions /skills/ e /progress/, que só tinham sido conferidos na mão."""
from rest_framework.test import APITestCase

from learning.models import ProgressRecord, StudentSkill
from subjects.models import Skill, Subject
from users.models import User

from .models import StudentProfile


class StudentProfileModelTests(APITestCase):
    def test_criacao_e_relacionamento_com_user(self):
        aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        perfil = StudentProfile.objects.create(user=aluno, grade_level="8º ano")
        self.assertEqual(aluno.student_profile, perfil)


class StudentAPITests(APITestCase):
    def setUp(self):
        self.aluno1 = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        self.aluno2 = User.objects.create_user(
            username="pedro", password="x", email="p@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="pr@t.com", role=User.Role.TEACHER)
        materia = Subject.objects.create(name="Matemática")
        self.skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno1, self.aluno2)
        StudentSkill.objects.create(student=self.aluno1, skill=self.skill, mastery_level=40)
        ProgressRecord.objects.create(student=self.aluno1, skill=self.skill,
                                       mastery_before=20, mastery_after=40, source="assessment")

    def test_aluno_so_lista_a_si_mesmo(self):
        self.client.force_authenticate(user=self.aluno1)
        resp = self.client.get("/api/students/")
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["id"], self.aluno1.id)

    def test_professor_lista_todos_os_alunos(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get("/api/students/")
        self.assertEqual(resp.data["count"], 2)

    def test_aluno_nao_consegue_ver_skills_de_outro_aluno_pela_url(self):
        """Mesmo trocando o {id} na URL manualmente, get_queryset() já
        filtra antes do get_object() — resultado é 404, não os dados."""
        self.client.force_authenticate(user=self.aluno2)
        resp = self.client.get(f"/api/students/{self.aluno1.id}/skills/")
        self.assertEqual(resp.status_code, 404)

    def test_aluno_ve_as_proprias_skills_e_progresso(self):
        self.client.force_authenticate(user=self.aluno1)
        resp_skills = self.client.get(f"/api/students/{self.aluno1.id}/skills/")
        self.assertEqual(resp_skills.status_code, 200)
        self.assertEqual(len(resp_skills.data), 1)
        self.assertEqual(resp_skills.data[0]["mastery_level"], 40)

        resp_progress = self.client.get(f"/api/students/{self.aluno1.id}/progress/")
        self.assertEqual(resp_progress.status_code, 200)
        self.assertEqual(len(resp_progress.data), 1)
