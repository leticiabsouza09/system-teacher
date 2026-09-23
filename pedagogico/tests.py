from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from classrooms.models import Classroom
from students.models import StudentProfile
from subjects.models import Subject
from users.models import User

from .models import LancamentoNota, RegistroFrequencia
from .services import (
    analisar_causa_raiz,
    calcular_alertas_aluno,
    processar_chamada_em_lote,
    salvar_grid_notas_em_lote,
)


def criar_aluno(username: str, turma: Classroom, matricula: str | None = None) -> User:
    aluno = User.objects.create_user(username=username, password="x", email=f"{username}@t.com",
                                      role=User.Role.STUDENT)
    StudentProfile.objects.create(user=aluno, grade_level="8º ano", matricula=matricula)
    turma.students.add(aluno)
    return aluno


class CalcularAlertasTests(APITestCase):
    def setUp(self):
        self.turma = Classroom.objects.create(name="8º Ano A")
        self.mat = Subject.objects.create(name="Matemática")
        self.aluno = criar_aluno("joana", self.turma)

    def test_sem_dado_nao_gera_alerta(self):
        self.assertEqual(calcular_alertas_aluno(self.aluno, 1), "")

    def test_frequencia_abaixo_de_75_gera_alerta(self):
        for i in range(10):
            RegistroFrequencia.objects.create(
                aluno=self.aluno, disciplina=self.mat, data=date(2026, 2, i + 1),
                bimestre=1, presente=(i < 6))
        self.assertIn("Frequência crítica", calcular_alertas_aluno(self.aluno, 1))

    def test_media_abaixo_de_6_gera_alerta(self):
        LancamentoNota.objects.create(aluno=self.aluno, disciplina=self.mat, bimestre=1, nota=Decimal("5.0"))
        self.assertIn("Média abaixo do mínimo", calcular_alertas_aluno(self.aluno, 1))

    def test_queda_de_20_por_cento_gera_alerta(self):
        LancamentoNota.objects.create(aluno=self.aluno, disciplina=self.mat, bimestre=1, nota=Decimal("8.0"))
        LancamentoNota.objects.create(aluno=self.aluno, disciplina=self.mat, bimestre=2, nota=Decimal("6.3"))
        self.assertIn("Queda de nota", calcular_alertas_aluno(self.aluno, 2))


class AnalisarCausaRaizTests(APITestCase):
    def setUp(self):
        self.turma = Classroom.objects.create(name="8º Ano A")
        self.mat = Subject.objects.create(name="Matemática")
        self.aluno = criar_aluno("joana", self.turma)

    def test_queda_real_identifica_causa_e_acao_curada(self):
        LancamentoNota.objects.create(aluno=self.aluno, disciplina=self.mat, bimestre=1, nota=Decimal("8.0"))
        LancamentoNota.objects.create(aluno=self.aluno, disciplina=self.mat, bimestre=2, nota=Decimal("5.0"))
        resultado = analisar_causa_raiz(self.aluno, self.mat)
        self.assertIn("Matemática", resultado["causa_raiz"])
        self.assertEqual(resultado["acao_recomendada"],
                          "Revisar operações e conceitos de base antes de avançar no conteúdo atual.")


class ProcessarChamadaEmLoteTests(APITestCase):
    def setUp(self):
        self.turma = Classroom.objects.create(name="8º Ano A")
        self.mat = Subject.objects.create(name="Matemática")
        self.a1 = criar_aluno("joana", self.turma)
        self.a2 = criar_aluno("pedro", self.turma)

    def test_lancamento_por_excecao(self):
        resultado = processar_chamada_em_lote(
            self.turma, self.mat, date(2026, 3, 1), bimestre=1, lista_ausentes_ids=[self.a2.id])
        self.assertEqual(resultado, {"presentes": 1, "ausentes": 1})
        self.assertTrue(RegistroFrequencia.objects.get(aluno=self.a1, data=date(2026, 3, 1)).presente)
        self.assertFalse(RegistroFrequencia.objects.get(aluno=self.a2, data=date(2026, 3, 1)).presente)


class SalvarGridNotasTests(APITestCase):
    def setUp(self):
        self.turma = Classroom.objects.create(name="8º Ano A")
        self.mat = Subject.objects.create(name="Matemática")
        self.aluno = criar_aluno("joana", self.turma)

    def test_transacao_atomica_reverte_tudo_se_uma_linha_falhar(self):
        with self.assertRaises(ValueError):
            salvar_grid_notas_em_lote([
                {"aluno_id": self.aluno.id, "disciplina_id": self.mat.id, "bimestre": 1, "nota": "7.0"},
                {"aluno_id": self.aluno.id, "disciplina_id": self.mat.id, "bimestre": 2, "nota": "-1.0"},
            ])
        self.assertEqual(LancamentoNota.objects.count(), 0)


class APIEndpointsTests(APITestCase):
    """Testa via requisição HTTP real, incluindo o isolamento de turma que
    a versão standalone não tinha (nenhuma permissão real lá)."""

    def setUp(self):
        self.professor = User.objects.create_user(
            username="prof_ana", password="x", email="p@t.com", role=User.Role.TEACHER)
        self.professor_de_fora = User.objects.create_user(
            username="prof_fora", password="x", email="pf@t.com", role=User.Role.TEACHER)
        self.turma = Classroom.objects.create(name="8º Ano A")
        self.turma.teachers.add(self.professor)
        self.mat = Subject.objects.create(name="Matemática")
        self.a1 = criar_aluno("joana", self.turma, matricula="MAT0001")
        self.a2 = criar_aluno("pedro", self.turma)

    def test_professor_vinculado_lanca_frequencia(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.post("/api/pedagogico/frequencia/em-lote/", {
            "turma": self.turma.id, "disciplina": self.mat.id,
            "data": "2026-03-01", "bimestre": 1, "ausentes": [self.a2.id],
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {"presentes": 1, "ausentes": 1})

    def test_professor_de_fora_nao_lanca_frequencia_da_turma(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.post("/api/pedagogico/frequencia/em-lote/", {
            "turma": self.turma.id, "disciplina": self.mat.id,
            "data": "2026-03-01", "bimestre": 1, "ausentes": [],
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_aluno_nao_acessa_nenhum_endpoint_do_pedagogico(self):
        self.client.force_authenticate(user=self.a1)
        resp = self.client.get(f"/api/pedagogico/painel-risco/?turma={self.turma.id}&bimestre=1")
        self.assertEqual(resp.status_code, 403)

    def test_professor_de_fora_nao_lanca_nota_de_aluno_que_nao_e_seu(self):
        self.client.force_authenticate(user=self.professor_de_fora)
        resp = self.client.post("/api/pedagogico/notas/grid/", {
            "notas": [{"aluno_id": self.a1.id, "disciplina_id": self.mat.id, "bimestre": 1, "nota": "8.0"}],
        }, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(LancamentoNota.objects.count(), 0)

    def test_painel_risco_traz_matricula_quando_existe(self):
        LancamentoNota.objects.create(aluno=self.a1, disciplina=self.mat, bimestre=1, nota=Decimal("4.0"))
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get(f"/api/pedagogico/painel-risco/?turma={self.turma.id}&bimestre=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]["matricula"], "MAT0001")

    def test_minhas_turmas_lista_so_as_turmas_do_professor_logado(self):
        outra_turma = Classroom.objects.create(name="Outra turma")
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get("/api/pedagogico/minhas-turmas/")
        self.assertEqual(resp.status_code, 200)
        nomes = [t["name"] for t in resp.data]
        self.assertIn(self.turma.name, nomes)
        self.assertNotIn(outra_turma.name, nomes)
        turma_resp = next(t for t in resp.data if t["id"] == self.turma.id)
        usernames = [a["username"] for a in turma_resp["students"]]
        self.assertCountEqual(usernames, ["joana", "pedro"])

    def test_minhas_turmas_bloqueada_para_aluno(self):
        self.client.force_authenticate(user=self.a1)
        resp = self.client.get("/api/pedagogico/minhas-turmas/")
        self.assertEqual(resp.status_code, 403)
