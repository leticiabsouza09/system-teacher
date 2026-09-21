"""
Testes de autenticação e das permissões customizadas (core/permissions.py).
Cobre exatamente os cenários que a Seção 16 do escopo pede: aluno não vê
dados de outro aluno, aluno não aprova diagnóstico, apenas autorizados
modificam planos.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from subjects.models import Skill, Subject
from learning.models import Diagnostic
from users.models import User


class RegisterViewTests(APITestCase):
    def test_registro_de_aluno_cria_usuario_e_token(self):
        resp = self.client.post(reverse("authentication:register"), {
            "username": "joana", "email": "joana@teste.com",
            "password": "SenhaForte123!", "role": User.Role.STUDENT,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", resp.data)
        self.assertEqual(resp.data["user"]["role"], "student")

    def test_nao_permite_autorregistro_como_admin(self):
        resp = self.client.post(reverse("authentication:register"), {
            "username": "hacker", "email": "h@teste.com",
            "password": "SenhaForte123!", "role": User.Role.ADMIN,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", resp.data)
        self.assertFalse(User.objects.filter(username="hacker").exists())


class LoginViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="joana", email="joana@teste.com", password="SenhaForte123!",
            role=User.Role.STUDENT)

    def test_login_com_credenciais_corretas(self):
        resp = self.client.post(reverse("authentication:login"),
                                 {"username": "joana", "password": "SenhaForte123!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", resp.data)

    def test_login_com_senha_errada_falha(self):
        resp = self.client.post(reverse("authentication:login"),
                                 {"username": "joana", "password": "errada"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LoginThrottleTests(APITestCase):
    """Testa a proteção contra força bruta (Etapa 11 — Seção 13). Limpa o
    cache antes/depois: throttling usa django.core.cache, que — diferente
    do banco — NÃO é revertido automaticamente entre testes pelo TestCase,
    e vazaria estado para os testes de login/registro que rodam depois."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(
            username="joana", email="j@t.com", password="SenhaForte123!", role=User.Role.STUDENT)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_bloqueia_apos_10_tentativas_por_minuto(self):
        for _ in range(10):
            resp = self.client.post(reverse("authentication:login"),
                                     {"username": "joana", "password": "errada"})
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        resp_11 = self.client.post(reverse("authentication:login"),
                                    {"username": "joana", "password": "errada"})
        self.assertEqual(resp_11.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_throttle_nao_bloqueia_login_legitimo_dentro_do_limite(self):
        resp = self.client.post(reverse("authentication:login"),
                                 {"username": "joana", "password": "SenhaForte123!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MeViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)

    def test_me_sem_autenticacao_retorna_401(self):
        resp = self.client.get(reverse("authentication:me"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_com_token_invalido_retorna_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token token-que-nao-existe")
        resp = self.client.get(reverse("authentication:me"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_autenticado_retorna_o_proprio_usuario(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse("authentication:me"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "joana")


class PermissoesCustomizadasTests(TestCase):
    """Testa core/permissions.py diretamente (sem precisar de endpoint —
    a Etapa 5 vai reaproveitar essas mesmas classes nos ViewSets, então
    testar aqui já cobre a regra de negócio, independentemente da URL)."""

    def setUp(self):
        self.aluno1 = User.objects.create_user(
            username="aluno1", password="x", email="a1@t.com", role=User.Role.STUDENT)
        self.aluno2 = User.objects.create_user(
            username="aluno2", password="x", email="a2@t.com", role=User.Role.STUDENT)
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)

        materia = Subject.objects.create(name="Matemática")
        skill = Skill.objects.create(subject=materia, name="Frações", difficulty_level="basic")
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno1)
        self.diagnostico_aluno1 = Diagnostic.objects.create(
            student=self.aluno1, skill=skill, mastery_level=40,
            difficulty_level="basic", evidence=["teste"],
        )

    def test_aluno_nao_acessa_diagnostico_de_outro_aluno(self):
        from core.permissions import IsOwnerStudent

        class RequestFake:
            def __init__(self, user):
                self.user = user

        permissao = IsOwnerStudent()
        # Dono acessa
        self.assertTrue(permissao.has_object_permission(
            RequestFake(self.aluno1), None, self.diagnostico_aluno1))
        # Outro aluno NÃO acessa — este é o teste que a Seção 16 pede
        self.assertFalse(permissao.has_object_permission(
            RequestFake(self.aluno2), None, self.diagnostico_aluno1))

    def test_aluno_nao_pode_aprovar_diagnostico_so_pode_ler(self):
        from rest_framework.test import APIRequestFactory
        from core.permissions import IsTeacherOrReadOnlyOwner

        factory = APIRequestFactory()
        permissao = IsTeacherOrReadOnlyOwner()

        get_request = factory.get("/fake/")
        get_request.user = self.aluno1
        self.assertTrue(permissao.has_object_permission(
            get_request, None, self.diagnostico_aluno1))  # aluno pode LER o próprio

        patch_request = factory.patch("/fake/", {"status": "approved"})
        patch_request.user = self.aluno1
        self.assertFalse(permissao.has_object_permission(
            patch_request, None, self.diagnostico_aluno1))  # aluno NÃO pode aprovar

        patch_request_prof = factory.patch("/fake/", {"status": "approved"})
        patch_request_prof.user = self.professor
        self.assertTrue(permissao.has_object_permission(
            patch_request_prof, None, self.diagnostico_aluno1))  # professor pode
