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


class ClassroomAPITests(APITestCase):
    """API de gerenciamento de turma — cobre exatamente as 4 regras de
    segurança documentadas em views.py."""

    def setUp(self):
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        self.outro_professor = User.objects.create_user(
            username="prof2", password="x", email="p2@t.com", role=User.Role.TEACHER)
        self.admin = User.objects.create_user(
            username="admin", password="x", email="a@t.com", role=User.Role.ADMIN)
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)

    def test_professor_cria_turma_e_e_adicionado_automaticamente(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/classrooms/", {"name": "8º Ano B"}, format="json")
        self.assertEqual(resp.status_code, 201)
        turma = Classroom.objects.get(pk=resp.data["id"])
        self.assertIn(self.professor, turma.teachers.all())

    def test_professor_nao_consegue_atribuir_outro_professor_na_criacao(self):
        """Regra 2: o campo teachers do payload é descartado pra não-admin."""
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/classrooms/", {
            "name": "8º Ano C", "teachers": [self.outro_professor.id],
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        turma = Classroom.objects.get(pk=resp.data["id"])
        self.assertIn(self.professor, turma.teachers.all())
        self.assertNotIn(self.outro_professor, turma.teachers.all())

    def test_aluno_nao_consegue_criar_turma(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.post("/api/classrooms/", {"name": "Turma Fantasma"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_professor_so_lista_as_proprias_turmas(self):
        minha = Classroom.objects.create(name="Minha turma")
        minha.teachers.add(self.professor)
        Classroom.objects.create(name="Turma do outro professor").teachers.add(self.outro_professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get("/api/classrooms/")
        nomes = [t["name"] for t in resp.data["results"]] if "results" in resp.data else \
            [t["name"] for t in resp.data]
        self.assertIn("Minha turma", nomes)
        self.assertNotIn("Turma do outro professor", nomes)

    def test_professor_nao_consegue_editar_turma_de_outro(self):
        """404, não 403 — get_queryset já filtra fora do alcance (mesmo
        padrão do isolamento aluno↔aluno usado no resto do projeto)."""
        turma_alheia = Classroom.objects.create(name="Não é minha")
        turma_alheia.teachers.add(self.outro_professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.patch(f"/api/classrooms/{turma_alheia.id}/", {"name": "Hackeada"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_professor_nao_consegue_se_auto_promover_a_dono_de_propria_turma_existente(self):
        """Regra 3: mesmo numa turma que o professor JÁ leciona, ele não
        pode mexer em `teachers` — só admin."""
        turma = Classroom.objects.create(name="Minha turma")
        turma.teachers.add(self.professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.patch(f"/api/classrooms/{turma.id}/",
                                  {"teachers": [self.professor.id, self.outro_professor.id]}, format="json")
        self.assertEqual(resp.status_code, 200)
        turma.refresh_from_db()
        self.assertNotIn(self.outro_professor, turma.teachers.all())

    def test_admin_consegue_editar_teachers(self):
        turma = Classroom.objects.create(name="Turma X")
        turma.teachers.add(self.professor)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f"/api/classrooms/{turma.id}/",
                                  {"teachers": [self.professor.id, self.outro_professor.id]}, format="json")
        self.assertEqual(resp.status_code, 200)
        turma.refresh_from_db()
        self.assertIn(self.outro_professor, turma.teachers.all())

    def test_professor_nao_consegue_substituir_o_roster_pelo_patch_generico(self):
        """A falha que corrigimos: 'students' também precisa ser
        descartado do payload pra não-admin — sem isso, um PATCH direto
        no endpoint genérico driblaria completamente o add-student/
        remove-student (que é por username, de propósito)."""
        turma = Classroom.objects.create(name="Minha turma")
        turma.teachers.add(self.professor)
        aluno_estranho = User.objects.create_user(
            username="intruso", password="x", email="i@t.com", role=User.Role.STUDENT)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.patch(f"/api/classrooms/{turma.id}/",
                                  {"students": [aluno_estranho.id]}, format="json")
        self.assertEqual(resp.status_code, 200)
        turma.refresh_from_db()
        self.assertNotIn(aluno_estranho, turma.students.all())

    def test_professor_nao_consegue_definir_roster_na_criacao(self):
        aluno_estranho = User.objects.create_user(
            username="intruso2", password="x", email="i2@t.com", role=User.Role.STUDENT)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/classrooms/", {
            "name": "Turma Nova", "students": [aluno_estranho.id],
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        turma = Classroom.objects.get(pk=resp.data["id"])
        self.assertNotIn(aluno_estranho, turma.students.all())

    def test_admin_consegue_editar_students_pelo_patch_generico(self):
        turma = Classroom.objects.create(name="Turma X")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f"/api/classrooms/{turma.id}/",
                                  {"students": [self.aluno.id]}, format="json")
        self.assertEqual(resp.status_code, 200)
        turma.refresh_from_db()
        self.assertIn(self.aluno, turma.students.all())

    def test_add_student_por_username(self):
        turma = Classroom.objects.create(name="Minha turma")
        turma.teachers.add(self.professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post(f"/api/classrooms/{turma.id}/add-student/",
                                 {"username": "joana"}, format="json")
        self.assertEqual(resp.status_code, 200)
        turma.refresh_from_db()
        self.assertIn(self.aluno, turma.students.all())

    def test_add_student_username_inexistente_da_404(self):
        turma = Classroom.objects.create(name="Minha turma")
        turma.teachers.add(self.professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post(f"/api/classrooms/{turma.id}/add-student/",
                                 {"username": "nao_existe"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_professor_nao_adiciona_aluno_em_turma_que_nao_e_sua(self):
        turma_alheia = Classroom.objects.create(name="Não é minha")
        turma_alheia.teachers.add(self.outro_professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post(f"/api/classrooms/{turma_alheia.id}/add-student/",
                                 {"username": "joana"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_remove_student(self):
        turma = Classroom.objects.create(name="Minha turma")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post(f"/api/classrooms/{turma.id}/remove-student/",
                                 {"username": "joana"}, format="json")
        self.assertEqual(resp.status_code, 200)
        turma.refresh_from_db()
        self.assertNotIn(self.aluno, turma.students.all())

    def test_professor_nao_consegue_excluir_turma(self):
        turma = Classroom.objects.create(name="Minha turma")
        turma.teachers.add(self.professor)
        self.client.force_authenticate(user=self.professor)
        resp = self.client.delete(f"/api/classrooms/{turma.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Classroom.objects.filter(pk=turma.id).exists())

    def test_admin_consegue_excluir_turma(self):
        turma = Classroom.objects.create(name="Turma a excluir")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"/api/classrooms/{turma.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Classroom.objects.filter(pk=turma.id).exists())
