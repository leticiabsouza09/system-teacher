"""Testes do NotesAnalysisService — a análise de anotações do professor."""
from rest_framework.test import APITestCase

from learning.models import TeacherFeedback
from users.models import User

from .notes_analyzer import MINIMUM_NOTES_FOR_ANALYSIS, NotesAnalysisService
from .provider import AIProvider


class NotesAnalysisServiceTests(APITestCase):
    def setUp(self):
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        self.outro_professor = User.objects.create_user(
            username="prof2", password="x", email="p2@t.com", role=User.Role.TEACHER)
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)

    def _criar_nota(self, professor, rating, comment):
        return TeacherFeedback.objects.create(
            teacher=professor, student=self.aluno, rating=rating, comment=comment)

    def test_sem_anotacoes_retorna_insuficiente(self):
        resultado = NotesAnalysisService().analyze(self.professor, self.aluno)
        self.assertEqual(resultado["status"], "insufficient_evidence")

    def test_uma_anotacao_ainda_insuficiente(self):
        self._criar_nota(self.professor, 3, "Primeira observação.")
        resultado = NotesAnalysisService().analyze(self.professor, self.aluno)
        self.assertEqual(resultado["status"], "insufficient_evidence")

    def test_duas_anotacoes_gera_analise_com_acoes_estruturadas(self):
        self._criar_nota(self.professor, 2, "Dificuldade recorrente.")
        self._criar_nota(self.professor, 2, "Continua com dificuldade.")
        resultado = NotesAnalysisService().analyze(self.professor, self.aluno)
        self.assertEqual(resultado["status"], "ok")
        self.assertEqual(resultado["notes_analyzed"], 2)
        self.assertEqual(resultado["average_rating"], 2.0)
        self.assertEqual(resultado["source"], "deterministic")
        # cada sugestão tem action + reason, não é mais string simples
        for acao in resultado["suggested_actions"]:
            self.assertIn("action", acao)
            self.assertIn("reason", acao)
        self.assertIn("disclaimer", resultado)
        self.assertIn("decisão", resultado["disclaimer"].lower())

    def test_so_analisa_anotacoes_do_proprio_professor(self):
        """Duas notas de OUTRO professor não devem contar para este."""
        self._criar_nota(self.outro_professor, 5, "Nota de outro professor.")
        self._criar_nota(self.outro_professor, 5, "Outra nota de outro professor.")
        resultado = NotesAnalysisService().analyze(self.professor, self.aluno)
        self.assertEqual(resultado["status"], "insufficient_evidence")

    def test_faixa_baixa_sugere_reavaliacao(self):
        self._criar_nota(self.professor, 1, "Muito ruim.")
        self._criar_nota(self.professor, 2, "Ainda ruim.")
        resultado = NotesAnalysisService().analyze(self.professor, self.aluno)
        self.assertIn("diagnóstico", resultado["suggested_actions"][0]["action"].lower())

    def test_faixa_alta_sugere_aumentar_desafio(self):
        self._criar_nota(self.professor, 5, "Excelente.")
        self._criar_nota(self.professor, 5, "Continua excelente.")
        resultado = NotesAnalysisService().analyze(self.professor, self.aluno)
        self.assertIn("desafio", resultado["suggested_actions"][0]["action"].lower())

    def test_ia_com_linguagem_clinica_e_descartada(self):
        class ProviderArriscado(AIProvider):
            def generate_structured(self, *a, **kw):
                return {"summary": "Pode ter TDAH.",
                        "suggested_actions": [{"action": "Avaliação psiquiátrica.", "reason": "Comportamento disperso."}]}

        self._criar_nota(self.professor, 2, "Disperso em aula.")
        self._criar_nota(self.professor, 2, "Continua disperso.")
        resultado = NotesAnalysisService(ai_provider=ProviderArriscado()).analyze(self.professor, self.aluno)
        self.assertEqual(resultado["source"], "deterministic")
        self.assertNotIn("tdah", resultado["summary"].lower())

    def test_ia_com_linguagem_segura_e_usada(self):
        class ProviderSeguro(AIProvider):
            def generate_structured(self, *a, **kw):
                return {
                    "summary": "Dificuldade recorrente com o conteúdo, mencionada em ambas as anotações.",
                    "suggested_actions": [
                        {"action": "Reforçar pré-requisitos.", "reason": "As anotações citam confusão com o método."},
                        {"action": "Propor exercícios extras.", "reason": "Reforço direcionado ajuda a consolidar a base."},
                    ],
                }

        self._criar_nota(self.professor, 2, "Disperso em aula.")
        self._criar_nota(self.professor, 2, "Continua disperso.")
        resultado = NotesAnalysisService(ai_provider=ProviderSeguro()).analyze(self.professor, self.aluno)
        self.assertEqual(resultado["source"], "ai")
        self.assertEqual(len(resultado["suggested_actions"]), 2)
        self.assertEqual(resultado["suggested_actions"][0]["action"], "Reforçar pré-requisitos.")

    def test_ia_com_acao_malformada_e_descartada_sem_quebrar(self):
        """Se a IA errar o schema (faltar 'reason', por exemplo), a ação
        malformada é descartada — não quebra a resposta inteira."""
        class ProviderSchemaErrado(AIProvider):
            def generate_structured(self, *a, **kw):
                return {
                    "summary": "Resumo válido, mas uma das ações veio incompleta.",
                    "suggested_actions": [
                        {"action": "Ação válida.", "reason": "Justificativa válida."},
                        {"action": "Ação sem motivo."},  # malformada — sem "reason"
                        "string solta",  # malformada — nem é dict
                    ],
                }

        self._criar_nota(self.professor, 2, "A.")
        self._criar_nota(self.professor, 2, "B.")
        resultado = NotesAnalysisService(ai_provider=ProviderSchemaErrado()).analyze(self.professor, self.aluno)
        self.assertEqual(resultado["source"], "ai")
        self.assertEqual(len(resultado["suggested_actions"]), 1)
        self.assertEqual(resultado["suggested_actions"][0]["action"], "Ação válida.")


class NotesAnalysisAPITests(APITestCase):
    def setUp(self):
        self.professor = User.objects.create_user(
            username="prof", password="x", email="p@t.com", role=User.Role.TEACHER)
        self.aluno = User.objects.create_user(
            username="joana", password="x", email="j@t.com", role=User.Role.STUDENT)
        from classrooms.models import Classroom
        turma = Classroom.objects.create(name="Turma Teste")
        turma.teachers.add(self.professor)
        turma.students.add(self.aluno)
        TeacherFeedback.objects.create(teacher=self.professor, student=self.aluno, rating=2, comment="A")
        TeacherFeedback.objects.create(teacher=self.professor, student=self.aluno, rating=2, comment="B")

    def test_aluno_nao_acessa_a_analise(self):
        self.client.force_authenticate(user=self.aluno)
        resp = self.client.get(f"/api/students/{self.aluno.id}/notes-analysis/")
        self.assertEqual(resp.status_code, 403)

    def test_professor_acessa_a_analise(self):
        self.client.force_authenticate(user=self.professor)
        resp = self.client.get(f"/api/students/{self.aluno.id}/notes-analysis/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "ok")
